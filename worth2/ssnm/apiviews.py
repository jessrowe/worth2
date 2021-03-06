from rest_framework import viewsets, permissions
from rest_framework_ember import parsers, renderers

from worth2.main.auth import AnySessionAuthentication
from worth2.ssnm.serializers import SupporterSerializer


class SupporterViewSet(viewsets.ModelViewSet):
    serializer_class = SupporterSerializer
    authentication_classes = (AnySessionAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (parsers.JSONParser,)
    renderer_classes = (renderers.JSONRenderer,)

    def get_queryset(self):
        return self.request.user.supporters.all()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
