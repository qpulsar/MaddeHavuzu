"""
Proje geneli pytest ayarları.

Django 4.2, Python 3.14'te `Context.__copy__` içinde `copy(super())` çağrısı
yüzünden AttributeError verir (Django 5.2.8+ ile düzeltildi). Test istemcisi
her render'da bağlamı kopyaladığından view testlerinin tamamı bu hatayla
düşer. Burada yalnızca o sürüm kombinasyonu için düzeltilmiş kopya kullanılır.
"""
import copy
import sys

import django

if sys.version_info >= (3, 14) and django.VERSION < (5, 2):
    from django.template.context import BaseContext

    def _base_context_copy(self):
        duplicate = object.__new__(self.__class__)
        duplicate.__dict__ = copy.copy(self.__dict__)
        duplicate.dicts = self.dicts[:]
        return duplicate

    BaseContext.__copy__ = _base_context_copy
