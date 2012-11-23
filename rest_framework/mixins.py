"""
Basic building blocks for generic class based views.

We don't bind behaviour to http method handlers yet,
which allows mixin classes to be composed in interesting ways.
"""
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.templatetags.rest_framework import replace_query_param
import itertools

class CreateModelMixin(object):
    """
    Create a model instance.
    Should be mixed in with any `BaseView`.
    """
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.DATA)
        if serializer.is_valid():
            self.pre_save(serializer.object)
            self.object = serializer.save()
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get_success_headers(self, data):
        if 'url' in data:
            return {'Location': data.get('url')}
        else:
            return {}
    
    def pre_save(self, obj):
        pass


class ListModelMixin(object):
    """
    List a queryset.
    Should be mixed in with `MultipleObjectAPIView`.
    """
    empty_error = u"Empty list and '%(class_name)s.allow_empty' is False."

    def parse_range_header(self, result_range):
        starts = []
        ends = []
        for result_range in result_range.split(","):
            start = end = None
            if result_range.startswith("-"):
                start = int(result_range)# + 1
            elif result_range.endswith("-"):
                start = int(result_range.split("-")[0])
            else:
                start, end = result_range.split("-")
                start, end = int(start), int(end) + 1
                
            starts.append(start)
            ends.append(end)
            
        return starts, ends
    
    def list(self, request, *args, **kwargs):
        self.object_list = self.get_filtered_queryset()
        status_code = None
        headers = {}
        partial_content = False
        
        try:
            # use querysets .count() to get quantity of elements
            records_count = self.object_list.count()
            
        except TypeError, AttributeError:
            # TypeError: []
            # AttributeError: obj.__len__ might be available
            records_count = len(self.object_list)

        # Default is to allow empty querysets.  This can be altered by setting
        # `.allow_empty = False`, to raise 404 errors on empty querysets.
        allow_empty = self.get_allow_empty()
        if not allow_empty and records_count == 0:
            error_args = {'class_name': self.__class__.__name__}
            raise Http404(self.empty_error % error_args)

        if 'HTTP_RANGE' in self.request.META:
            token, result_range = self.request.META['HTTP_RANGE'].split("=")
            if token == self.settings.PAGINATION_RANGE_HEADER_TOKEN:                
                try:
                    ranges = []
                    records_start, records_end = self.parse_range_header(result_range)
                    
                    for range_start, range_end in zip(records_start, records_end):
                        if range_start is not None and range_start < 0:
                            # Querystes don't support negative indexing (yet?)
                            range_start = records_count + range_start
                            
                        ranges.append((range_start,range_end))
                        
                    if len(ranges) > 1:
                        raise Exception # currently not available
                except:
                    return Response(status=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE)
                
                # ranges can be comma seperated, so multiple lists are possibly requested
                limited_object_list = itertools.chain(*[
                    self.object_list[record_start:record_end]
                    for record_start,record_end
                    in ranges
                ])
                
                serializer = self.get_serializer(limited_object_list)
                partial_content = True
            else:
                return Response(status=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE)
        else:
            
            # Pagination size is set by the `.paginate_by` attribute,
            # which may be `None` to disable pagination.
            page_size = self.get_paginate_by(self.object_list)
            page_nr = int(self.request.GET.get('page',0))
            
            if page_size:
                packed = self.paginate_queryset(self.object_list, page_size)
                paginator, page, queryset, is_paginated = packed
                
                if self.settings.PAGINATION_IN_HEADER:
                    headers['Link'] = headers.get('Link', '')
                    url = self.request and self.request.build_absolute_uri() or ''
                    first_url = replace_query_param(url, 'page', 1)
                    if len(headers['Link']):
                        headers['Link'] += ', '
                    headers['Link'] += '<%(url)s>; rel="first"' % {'url': first_url}
                    last_url = replace_query_param(url, 'page', paginator.num_pages)
                    headers['Link'] += ', <%(url)s>; rel="last"' % {'url': last_url}
            
            if page_size and page_nr:
                if self.settings.PAGINATION_IN_HEADER:
                    ranges = (((page.number - 1) * page_size, page.number * page_size),)
                    
                    limited_object_list = itertools.chain(*[
                        self.object_list[record_start:record_end]
                        for record_start,record_end
                        in ranges
                    ])
                    serializer = self.get_serializer(limited_object_list)
                    if page.has_other_pages():
                        url = self.request and self.request.build_absolute_uri() or ''
                        if page.has_next():
                            next_url = replace_query_param(url, 'page', page.next_page_number())
                            headers['Link'] += ', <%(url)s>; rel="next"' % {'url': next_url}
                        if page.has_previous():
                            prev_url = replace_query_param(url, 'page', page.previous_page_number())
                            headers['Link'] += ', <%(url)s>; rel="previous"' % {'url': prev_url}
                else:                    
                    serializer = self.get_pagination_serializer(page)
            else:
                serializer = self.get_serializer(self.object_list)
                
                headers['Accept-Ranges'] = self.settings.PAGINATION_RANGE_HEADER_TOKEN
    
        if partial_content:
            status_code = status.HTTP_206_PARTIAL_CONTENT
            
            # currently just 1 range processable
            cur_range = ranges[0]
            
            headers['Content-Range'] = '%(token)s %(records_start)d-%(records_end)d/%(records_count)d' % {
                                'token': self.settings.PAGINATION_RANGE_HEADER_TOKEN,
                                'records_count': records_count,
                                'records_start': cur_range[0] or 0,
                                'records_end': min((cur_range[1] - 1) if cur_range[1] is not None else records_count,records_count-1),
                            }
            headers['Accept-Ranges'] = self.settings.PAGINATION_RANGE_HEADER_TOKEN
        
        return Response(serializer.data, status=status_code, headers=headers)
    def get_paginate_by(self,object_list):
        return int(self.request.GET.get('pagesize',super(ListModelMixin,self).get_paginate_by(object_list)) or 0)
    
    def metadata(self, request):
        metadata = super(ListModelMixin,self).metadata(request)
        if not 'Accept-Ranges' in metadata:
            metadata['Accept-Ranges'] = []
        if not self.settings.PAGINATION_RANGE_HEADER_TOKEN in metadata['Accept-Ranges']:
            metadata['Accept-Ranges'].append(self.settings.PAGINATION_RANGE_HEADER_TOKEN)
        return metadata

class RetrieveModelMixin(object):
    """
    Retrieve a model instance.
    Should be mixed in with `SingleObjectBaseView`.
    """
    def retrieve(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(self.object)
        return Response(serializer.data)


class UpdateModelMixin(object):
    """
    Update a model instance.
    Should be mixed in with `SingleObjectBaseView`.
    """
    def update(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()
            success_status = status.HTTP_200_OK
        except Http404:
            self.object = None
            success_status = status.HTTP_201_CREATED

        serializer = self.get_serializer(self.object, data=request.DATA)

        if serializer.is_valid():
            self.pre_save(serializer.object)
            self.object = serializer.save()
            return Response(serializer.data, status=success_status)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def pre_save(self, obj):
        """
        Set any attributes on the object that are implicit in the request.
        """
        # pk and/or slug attributes are implicit in the URL.
        pk = self.kwargs.get(self.pk_url_kwarg, None)
        if pk:
            setattr(obj, 'pk', pk)

        slug = self.kwargs.get(self.slug_url_kwarg, None)
        if slug:
            slug_field = self.get_slug_field()
            setattr(obj, slug_field, slug)


class DestroyModelMixin(object):
    """
    Destroy a model instance.
    Should be mixed in with `SingleObjectBaseView`.
    """
    def destroy(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
