from grading.services.statistics import StatisticsService
from itempool.models import ItemAnalysisResult, ItemInstance

class ItemAnalysisService:
    """
    Maddelerin uygulama sonuçlarını analiz eden ve ItemAnalysisResult modellerini güncelleyen servis.
    """
    
    def process_session_results(self, session, item_mapping: dict, test_form=None):
        """
        Bir UploadSession'daki sonuçları maddelerle eşleştirip analiz sonuçlarını kaydeder.
        
        :param session: grading.models.UploadSession nesnesi
        :param item_mapping: {soru_sirasi: ItemInstance_id} sözlüğü (soru_sirasi 0-tabanlıdır)
        :param test_form: (Opsiyonel) TestForm nesnesi
        """
        stats_service = StatisticsService()
        results = session.results.all()
        
        if not results.exists():
            return 0
            
        # StatisticsService'den temel analiz verilerini al (p ve r değerleri)
        item_analysis_data = stats_service._calculate_item_analysis(session, results)
        
        processed_count = 0
        for data in item_analysis_data:
            # Soru numarası 1-tabanlı geliyor
            q_idx = data['question_number'] - 1
            instance_id = item_mapping.get(q_idx)
            
            if not instance_id:
                continue
                
            try:
                instance = ItemInstance.objects.get(id=instance_id)
                
                # Çeldirici verimliliği hesapla (basit: doğru şık dışındaki şıkların seçilme oranı)
                # Daha detaylı analiz için option_counts kullanılabilir
                correct_ans = data['correct_answer']
                option_counts = data['option_counts']
                total_responses = sum(option_counts.values())
                
                incorrect_responses = total_responses - option_counts.get(correct_ans, 0)
                dist_eff = (incorrect_responses / total_responses) if total_responses > 0 else 0
                
                analysis_result = ItemAnalysisResult.objects.create(
                    item_instance=instance,
                    upload_session=session,
                    test_form=test_form,
                    difficulty_p=data['p'],
                    discrimination_r=data['r'],
                    distractor_efficiency=dist_eff,
                    analysis_data_json=data
                )
                
                analysis_result.calculate_risk()
                analysis_result.save()
                processed_count += 1
                
            except ItemInstance.DoesNotExist:
                continue
                
        return processed_count

    @staticmethod
    def get_risk_color(score):
        """Risk skoruna göre Bootstrap class döner."""
        if score <= 30:
            return "success" # Yeşil
        elif score <= 60:
            return "warning" # Sarı
        else:
            return "danger"  # Kırmızı
