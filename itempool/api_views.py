from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models.pool import ItemPool, LearningOutcome
from .serializers import LearningOutcomeSerializer

class LearningOutcomeListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = LearningOutcomeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        pool_id = self.kwargs.get('pool_id')
        return LearningOutcome.objects.filter(pool_id=pool_id).order_by('order', 'code')

    def perform_create(self, serializer):
        pool_id = self.kwargs.get('pool_id')
        pool = get_object_or_404(ItemPool, id=pool_id)
        # Sadece havuz sahibi veya yetkili biri ekleyebilir kontrolü eklenebilir
        serializer.save(pool=pool)

class LearningOutcomeRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = LearningOutcome.objects.all()
    serializer_class = LearningOutcomeSerializer
    permission_classes = [IsAuthenticated]
