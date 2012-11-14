from django.core.handlers.wsgi import STATUS_CODE_TEXT
from django.template.response import SimpleTemplateResponse
from rest_framework.settings import api_settings


class Response(SimpleTemplateResponse):
    """
    An HttpResponse that allows it's data to be rendered into
    arbitrary media types.
    """
    # see http://tools.ietf.org/html/rfc5988
    reserved_link_relations = ['alternate', 'appendix', 'bookmark', 'chapter', 'contents', 'copyright', 'current',
                             'describedby', 'edit', 'edit-media', 'enclosure', 'first', 'glossary', 'help', 'hub',
                             'index', 'last', 'latest-version', 'license', 'next', 'next-archive', 'payment',
                             'prev', 'predecessor-version', 'previous', 'prev-archive', 'related', 'replies',
                             'section', 'self', 'service', 'start', 'stylesheet', 'subsection', 'successor-version',
                             'up', 'version-history', 'via', 'working-copy', 'working-copy-of']

    def __init__(self, data=None, status=200,
                 template_name=None, headers=None,
                 exception=False):
        """
        Alters the init arguments slightly.
        For example, drop 'template_name', and instead use 'data'.

        Setting 'renderer' and 'media_type' will typically be defered,
        For example being set automatically by the `APIView`.
        """
        super(Response, self).__init__(None, status=status)
        self.data = data
        self.template_name = template_name
        self.exception = exception
<<<<<<< HEAD
<<<<<<< HEAD
        
=======
                
>>>>>>> generic_redirect_view
        if headers:
            for name,value in headers.iteritems():
                self[name] = value
=======
        
        if isinstance(self.data,dict) and api_settings.RESPONSE_LINK_HEADER:
            self.prepare_link_header()
    
    def prepare_link_header(self):
        header_links = []
        for key, value in self.data.iteritems():
            if isinstance(value,basestring) and (value.startswith('http://') or value.startswith('https://')):
                if key in self.reserved_link_relations:
                    header_links.append({'iri': value, 'rel': key})
                else:
                    header_links.append({'iri': value, 'rel': 'related', 'title': key})
                if api_settings.RESPONSE_LINK_HEADER == "exclusive":
                    self.data.pop(key)
                    
        if header_links:
            link_header = self.get('Link', self.unpack_link_header(header_links.pop(0)))
            for link in header_links:
                link_header += ', ' + self.unpack_link_header(link)
                
            self['Link'] = link_header
    
    def unpack_link_header(self, link_dict):
        iri = link_dict.pop('iri')
        # TODO escape/quote?
        params = "; ".join('%(key)s="%(value)s"' % {'key': key, 'value': value} for key, value in link_dict.iteritems())
        return '<%(iri)s>; %(params)s' % {'iri': iri, 'params': params}
>>>>>>> link_header_support

    @property
    def rendered_content(self):
        renderer = getattr(self, 'accepted_renderer', None)
        media_type = getattr(self, 'accepted_media_type', None)
        context = getattr(self, 'renderer_context', None)

        assert renderer, ".accepted_renderer not set on Response"
        assert media_type, ".accepted_media_type not set on Response"
        assert context, ".renderer_context not set on Response"
        context['response'] = self

        self['Content-Type'] = media_type
        return renderer.render(self.data, media_type, context)

    @property
    def status_text(self):
        """
        Returns reason text corresponding to our HTTP response status code.
        Provided for convenience.
        """
        # TODO: Deprecate and use a template tag instead
        # TODO: Status code text for RFC 6585 status codes
        return STATUS_CODE_TEXT.get(self.status_code, '')

    def __getstate__(self):
        """
        Remove attributes from the response that shouldn't be cached
        """
        state = super(Response, self).__getstate__()
        for key in ('accepted_renderer', 'renderer_context', 'data'):
            if key in state:
                del state[key]
        return state
