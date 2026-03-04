import os
import django
from django.test import Client

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "maddehavuzu.settings")
django.setup()

client = Client()
client.login(username='emin', password='1234')

# First, fetch default (Turkish)
response = client.get('/havuz/')
html_tr = response.content.decode('utf-8')
print("TR IN HTML:", "Madde Havuzları" in html_tr, "| Dashboard IN HTML:", "Panel" in html_tr)

# Now with English
client.cookies.load({'django_language': 'en'})
response = client.get('/havuz/')
html_en = response.content.decode('utf-8')
print("EN IN HTML:", "Item Pools" in html_en, "| Dashboard IN HTML:", "Dashboard" in html_en)

