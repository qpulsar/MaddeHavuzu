from rest_framework import serializers
from .models.pool import LearningOutcome

class LearningOutcomeSerializer(serializers.ModelSerializer):
    level_display = serializers.CharField(source='get_level_display', read_only=True)

    class Meta:
        model = LearningOutcome
        fields = [
            'id', 'pool', 'code', 'description', 'level', 
            'level_display', 'weight', 'order', 'is_active'
        ]
        read_only_fields = ['id', 'pool']
