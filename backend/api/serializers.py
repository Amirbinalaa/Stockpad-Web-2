from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.db.utils import OperationalError
from .models import (
    User, Profile, Category, Material, MaterialRequest,
    Product, BOMItem, ProductionPlan, ProductionPlanItem, MaterialRequirement,
    Supplier, ProcurementRequest, ProcurementOrder, RequestStatusHistory,
    ChatMessage, ChatConversation,
)


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ('id', 'conversation', 'message', 'reply', 'timestamp')
        read_only_fields = ('id', 'timestamp')

class ChatConversationSerializer(serializers.ModelSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = ChatConversation
        fields = ('id', 'title', 'created_at', 'updated_at', 'messages', 'message_count')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def get_message_count(self, obj):
        return obj.messages.count()


# ─────────────────────────────────────────────
# AUTH / USER
# ─────────────────────────────────────────────

class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Accept email or username in the `username` field for JWT login."""

    def validate(self, attrs):
        username = (attrs.get(self.username_field) or "").strip()
        password = attrs.get("password")
        if not username or not password:
            raise serializers.ValidationError("Email/username and password are required.")

        try:
            return super().validate(attrs)
        except serializers.ValidationError:
            raise
        except OperationalError as exc:
            raise serializers.ValidationError(
                "Authentication service temporarily unavailable. Check database connectivity."
            ) from exc


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = Profile
        fields = ('id', 'user', 'username', 'email', 'full_name', 'phone_number',
                  'profile_picture', 'role', 'department')
        read_only_fields = ('id', 'user')


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)
    role = serializers.CharField(source='profile.role', required=False)
    # Use different names for reading and writing to avoid source conflicts
    avatar_url = serializers.ImageField(source='profile.profile_picture', read_only=True)
    avatar = serializers.ImageField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'profile', 'role', 'avatar', 'avatar_url')
        read_only_fields = ('id',)

    def update(self, instance, validated_data):
        avatar = validated_data.pop('avatar', None)
        profile_data = validated_data.pop('profile', {})
        
        # Update user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        profile = instance.profile
        if avatar:
            profile.profile_picture = avatar
            
        if 'role' in profile_data:
            profile.role = profile_data['role']
            
        profile.save()

        return instance


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    role = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ('username', 'password', 'email', 'role')

    def create(self, validated_data):
        role = validated_data.pop('role', 'Engineer')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        user.profile.role = role
        user.profile.save()
        return user


# ─────────────────────────────────────────────
# CATEGORIES
# ─────────────────────────────────────────────

class CategorySerializer(serializers.ModelSerializer):
    material_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ('id', 'name', 'material_count')
        read_only_fields = ('id',)

    def get_material_count(self, obj):
        return obj.material_set.count()


# ─────────────────────────────────────────────
# MATERIALS
# ─────────────────────────────────────────────

class MaterialListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    category_name = serializers.CharField(source='category.name', read_only=True)
    needs_reorder = serializers.SerializerMethodField()
    quantity = serializers.IntegerField(source='quantity_available', read_only=True)
    stock_status = serializers.ReadOnlyField(source='status')

    class Meta:
        model = Material
        fields = ('id', 'name', 'code', 'category', 'category_name',
                  'quantity_available', 'quantity', 'unit', 'status', 'stock_status', 
                  'unit_cost', 'needs_reorder', 'last_updated')

    def get_needs_reorder(self, obj):
        return obj.needs_reorder


class MaterialSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')
    quantity = serializers.IntegerField(source='quantity_available', read_only=True)
    stock_status = serializers.ReadOnlyField(source='status')
    stock_value = serializers.SerializerMethodField()
    needs_reorder = serializers.SerializerMethodField()

    class Meta:
        model = Material
        fields = (
            'id', 'name', 'category', 'category_name', 'code', 'description', 'specifications',
            'quantity_available', 'quantity', 'unit', 'min_stock_level',
            'unit_cost', 'supplier', 'location',
            'status', 'stock_status', 'last_updated', 'image',
            'stock_value', 'needs_reorder',
        )
        read_only_fields = ('quantity_available',)

    def get_stock_value(self, obj):
        return float(obj.stock_value)

    def get_needs_reorder(self, obj):
        return obj.needs_reorder

    def validate_quantity_available(self, value):
        if value < 0:
            raise serializers.ValidationError("Quantity available cannot be negative.")
        return value

    def validate_unit_cost(self, value):
        if value < 0:
            raise serializers.ValidationError("Unit cost must be positive.")
        return value


class FlexibleMaterialPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """
    PrimaryKeyRelatedField for Material that accepts:
    1. Local Material PK (id)
    2. Remote WM Material PK (site_a_material_id)
    3. Auto-creates local Material row if site_a_material_id is provided but not yet in DB.
    """
    def to_internal_value(self, data):
        # 1. Standard PK lookup in local Material table
        try:
            return super().to_internal_value(data)
        except serializers.ValidationError:
            pass

        # 2. Check site_a_material_id lookup
        site_a_id = None
        if isinstance(data, (int, str)) and str(data).isdigit():
            site_a_id = int(data)

        initial_data = getattr(self.parent, 'initial_data', {}) if self.parent else {}
        if not site_a_id and isinstance(initial_data, dict):
            raw_site_a = initial_data.get('site_a_material_id')
            if raw_site_a and str(raw_site_a).isdigit():
                site_a_id = int(raw_site_a)

        if site_a_id is not None:
            mat = Material.objects.filter(site_a_material_id=site_a_id).first()
            if mat:
                return mat

            # 3. Auto-provision local Material if not present
            mat_name = ''
            unit = 'Units'
            if isinstance(initial_data, dict):
                mat_name = initial_data.get('material_name') or ''
                unit = initial_data.get('unit') or 'Units'
            if not mat_name:
                mat_name = f"Material #{site_a_id}"

            default_cat, _ = Category.objects.get_or_create(name="General")
            mat, _ = Material.objects.get_or_create(
                site_a_material_id=site_a_id,
                defaults={
                    'name': mat_name,
                    'category': default_cat,
                    'unit': unit,
                    'quantity_available': 0,
                    'status': 'In Stock',
                }
            )
            return mat

        raise serializers.ValidationError(f"Invalid material identifier: {data}")


class MaterialRequestSerializer(serializers.ModelSerializer):
    material = FlexibleMaterialPrimaryKeyRelatedField(queryset=Material.objects.all())
    material_name = serializers.ReadOnlyField(source='material.name')
    requested_by_name = serializers.ReadOnlyField(source='requested_by.username')
    approved_by_name = serializers.ReadOnlyField(source='approved_by.username')
    quantity = serializers.IntegerField(source='quantity_needed', read_only=True)
    notes = serializers.CharField(source='justification', read_only=True)

    class Meta:
        model = MaterialRequest
        fields = (
            'id', 'material', 'material_name', 'requested_by', 'requested_by_name',
            'quantity_needed', 'quantity', 'justification', 'notes', 'status',
            'request_date', 'rejection_reason', 'approved_by', 'approved_by_name', 'approved_date',
            'site_a_request_id', 'sync_status',
        )
        read_only_fields = ('id', 'requested_by', 'status', 'request_date',
                            'rejection_reason', 'approved_by', 'approved_date',
                            'site_a_request_id', 'sync_status')

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value


class RequestStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.ReadOnlyField(source='changed_by.username')

    class Meta:
        model = RequestStatusHistory
        fields = ('id', 'request', 'old_status', 'new_status', 'changed_by',
                  'changed_by_name', 'notes', 'changed_at')
        read_only_fields = ('id', 'changed_at')


# ─────────────────────────────────────────────
# BOM
# ─────────────────────────────────────────────

class BOMItemSerializer(serializers.ModelSerializer):
    material_name = serializers.ReadOnlyField(source='material.name')
    quantity_with_waste = serializers.SerializerMethodField()
    total_cost_per_unit = serializers.SerializerMethodField()

    class Meta:
        model = BOMItem
        fields = ('id', 'product', 'material', 'material_name', 'quantity_per_unit',
                  'waste_factor', 'category', 'is_active',
                  'quantity_with_waste', 'total_cost_per_unit', 'created_at')
        read_only_fields = ('id', 'created_at')

    def get_quantity_with_waste(self, obj):
        return round(obj.quantity_with_waste, 4)

    def get_total_cost_per_unit(self, obj):
        return round(obj.total_cost_per_unit, 2)


class ProductSerializer(serializers.ModelSerializer):
    bom_items = BOMItemSerializer(many=True, read_only=True)
    total_materials = serializers.SerializerMethodField()
    calculated_cost = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ('id', 'name', 'code', 'description', 'category', 'version',
                  'estimated_cost_per_unit', 'production_time_days', 'is_active',
                  'total_materials', 'calculated_cost', 'bom_items', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def get_total_materials(self, obj):
        return obj.total_materials

    def get_calculated_cost(self, obj):
        return round(obj.calculated_cost, 2)


class ProductionPlanItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    completion_percentage = serializers.SerializerMethodField()

    class Meta:
        model = ProductionPlanItem
        fields = ('id', 'plan', 'product', 'product_name', 'quantity', 'priority',
                  'start_week', 'duration_weeks', 'completed_quantity',
                  'completion_percentage', 'is_active')
        read_only_fields = ('id',)

    def get_completion_percentage(self, obj):
        return round(obj.completion_percentage, 1)


class MaterialRequirementSerializer(serializers.ModelSerializer):
    material_name = serializers.ReadOnlyField(source='material.name')

    class Meta:
        model = MaterialRequirement
        fields = ('id', 'plan', 'material', 'material_name', 'total_required',
                  'current_stock', 'shortage', 'unit_cost', 'total_cost',
                  'shortage_value', 'urgency', 'calculated_at')
        read_only_fields = ('id', 'calculated_at')


class ProductionPlanSerializer(serializers.ModelSerializer):
    plan_items = ProductionPlanItemSerializer(many=True, read_only=True)
    requirements = MaterialRequirementSerializer(many=True, read_only=True)
    created_by_name = serializers.ReadOnlyField(source='created_by.username')
    duration_days = serializers.SerializerMethodField()

    class Meta:
        model = ProductionPlan
        fields = ('id', 'name', 'description', 'start_date', 'end_date', 'status',
                  'created_by', 'created_by_name', 'duration_days',
                  'plan_items', 'requirements', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_by', 'created_at', 'updated_at')

    def get_duration_days(self, obj):
        return obj.duration_days


# ─────────────────────────────────────────────
# SUPPLIERS & PROCUREMENT
# ─────────────────────────────────────────────

class SupplierSerializer(serializers.ModelSerializer):
    is_highly_reliable = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = ('id', 'name', 'contact_person', 'email', 'phone',
                  'lead_time_days', 'min_order_value', 'reliability_score',
                  'specialties', 'is_active', 'is_highly_reliable', 'created_at')
        read_only_fields = ('id', 'created_at')

    def get_is_highly_reliable(self, obj):
        return obj.is_highly_reliable


class ProcurementRequestSerializer(serializers.ModelSerializer):
    material_name = serializers.ReadOnlyField(source='material.name')
    requested_by_name = serializers.ReadOnlyField(source='requested_by.username')
    approved_by_name = serializers.ReadOnlyField(source='approved_by.username')

    class Meta:
        model = ProcurementRequest
        fields = ('id', 'material', 'material_name', 'requested_amount', 'current_stock',
                  'shortage_amount', 'estimated_cost', 'priority', 'requested_by',
                  'requested_by_name', 'notes', 'status', 'created_at', 'updated_at',
                  'submitted_at', 'approved_at', 'approved_by', 'approved_by_name',
                  'expected_delivery_date')
        read_only_fields = ('id', 'requested_by', 'created_at', 'updated_at',
                            'submitted_at', 'approved_at', 'approved_by')


class ProcurementOrderSerializer(serializers.ModelSerializer):
    supplier_name = serializers.ReadOnlyField(source='supplier.name')

    class Meta:
        model = ProcurementOrder
        fields = ('id', 'supplier', 'supplier_name', 'total_amount', 'total_cost',
                  'status', 'order_date', 'expected_delivery_date', 'actual_delivery_date',
                  'notes', 'supplier_order_number', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')
