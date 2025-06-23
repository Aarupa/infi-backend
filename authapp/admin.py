from django.contrib import admin

from authapp.models import ContactUs, Register

# Register your models here.
admin.site.register(Register)
admin.site.register(ContactUs)