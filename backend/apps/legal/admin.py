from django.contrib import admin

from .models import LegalDocument, UserLegalAcceptance


@admin.register(LegalDocument)
class LegalDocumentAdmin(admin.ModelAdmin):
    list_display = ("type", "version", "effective_at")
    list_filter = ("type",)

    def has_change_permission(self, request, obj=None):
        return obj is None and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UserLegalAcceptance)
class UserLegalAcceptanceAdmin(admin.ModelAdmin):
    list_display = ("user", "document", "accepted_at")
    list_select_related = ("user", "document")
    raw_id_fields = ("user", "document")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
