from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, Profile, Category, Material, MaterialRequest, RequestStatusHistory,
    Product, BOMItem, ProductionPlan, ProductionPlanItem, MaterialRequirement,
    Supplier, ProcurementRequest, ProcurementOrder,
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'get_role', 'is_staff')

    def get_role(self, obj):
        return obj.profile.role if hasattr(obj, 'profile') else '-'
    get_role.short_description = 'Role'

    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ()}),
    )


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'role', 'department', 'phone_number')
    list_filter = ('role',)
    search_fields = ('user__username', 'full_name')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'material_count')
    search_fields = ('name',)

    def material_count(self, obj):
        return obj.material_set.count()
    material_count.short_description = 'Materials'


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'quantity_available', 'unit', 'status', 'needs_reorder_display')
    list_filter = ('category', 'status')
    search_fields = ('name', 'code', 'supplier')
    readonly_fields = ('last_updated',)

    def needs_reorder_display(self, obj):
        return '⚠️ Yes' if obj.needs_reorder else 'No'
    needs_reorder_display.short_description = 'Needs Reorder'


@admin.register(MaterialRequest)
class MaterialRequestAdmin(admin.ModelAdmin):
    list_display = ('material', 'requested_by', 'quantity_needed', 'status', 'request_date')
    list_filter = ('status',)
    search_fields = ('material__name', 'requested_by__username')
    readonly_fields = ('request_date',)


@admin.register(RequestStatusHistory)
class RequestStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('request', 'old_status', 'new_status', 'changed_by', 'changed_at')
    list_filter = ('new_status',)
    readonly_fields = ('changed_at',)


# ── BOM ─────────────────────────────────────
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'category', 'version', 'is_active', 'total_materials')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'code')

    def total_materials(self, obj):
        return obj.total_materials
    total_materials.short_description = 'BOM Items'


@admin.register(BOMItem)
class BOMItemAdmin(admin.ModelAdmin):
    list_display = ('product', 'material', 'quantity_per_unit', 'waste_factor', 'category', 'is_active')
    list_filter = ('category', 'is_active', 'product')
    search_fields = ('material__name', 'product__name')


@admin.register(ProductionPlan)
class ProductionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'start_date', 'end_date', 'created_by')
    list_filter = ('status',)
    search_fields = ('name',)


@admin.register(ProductionPlanItem)
class ProductionPlanItemAdmin(admin.ModelAdmin):
    list_display = ('plan', 'product', 'quantity', 'priority', 'completed_quantity')
    list_filter = ('priority', 'plan')


@admin.register(MaterialRequirement)
class MaterialRequirementAdmin(admin.ModelAdmin):
    list_display = ('plan', 'material', 'total_required', 'shortage', 'urgency')
    list_filter = ('urgency', 'plan')


# ── Suppliers & Procurement ──────────────────
@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'email', 'reliability_score', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'email', 'contact_person')


@admin.register(ProcurementRequest)
class ProcurementRequestAdmin(admin.ModelAdmin):
    list_display = ('material', 'requested_amount', 'priority', 'status', 'created_at')
    list_filter = ('status', 'priority')
    search_fields = ('material__name',)


@admin.register(ProcurementOrder)
class ProcurementOrderAdmin(admin.ModelAdmin):
    list_display = ('supplier', 'total_amount', 'status', 'order_date', 'expected_delivery_date')
    list_filter = ('status', 'supplier')
    search_fields = ('supplier__name', 'supplier_order_number')
