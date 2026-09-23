"""
Optik/Kopya yetki yardımcıları.

Kaynak modülde "instructor"/"admin" rolleri vardı. Bu projede onaylı her
kullanıcı öğretim elemanıdır; yönetici = superuser, staff veya profil rolü ADMIN.
Kaynakta eksik olan sahiplik kontrolü burada zorunludur: kullanıcı yalnızca
kendi testlerini görür, yönetici hepsini.
"""
from django.core.exceptions import PermissionDenied
from django.http import Http404

from optik import store


def is_admin(user) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    profile = getattr(user, 'profile', None)
    return getattr(profile, 'role', None) == 'ADMIN'


def get_test_for_user(user, test_id: str):
    """OptikTest nesnesini sahiplik kontrolüyle döndür (yoksa 404, yetkisizse 403)."""
    try:
        test = store.get_test_obj(test_id)
    except store.NotFound:
        raise Http404("Test bulunamadı")
    if test.deleted:
        raise Http404("Test bulunamadı")
    if test.owner_id != user.id and not is_admin(user):
        raise PermissionDenied("Bu teste erişim yetkiniz yok.")
    return test


def get_batch_for_user(user, batch_id: str):
    """OptikBatch nesnesini sahiplik kontrolüyle döndür."""
    try:
        batch = store.get_batch_obj(batch_id)
    except store.NotFound:
        raise Http404("Batch bulunamadı")
    if batch.test.deleted:
        raise Http404("Batch bulunamadı")
    if batch.test.owner_id != user.id and not is_admin(user):
        raise PermissionDenied("Bu batch'e erişim yetkiniz yok.")
    return batch


