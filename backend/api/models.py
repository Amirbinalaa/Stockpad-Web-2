from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import MinValueValidator
import uuid


# ─────────────────────────────────────────────
# USERS & PROFILES
# ─────────────────────────────────────────────

class User(AbstractUser):
    email = models.EmailField(unique=True)
    REQUIRED_FIELDS = ['email']


class Profile(models.Model):
    ROLE_CHOICES = [
        ('Engineer', 'Engineer'),
        ('warehouse', 'Warehouse'),
        ('Manager', 'Manager'),
        ('Worker', 'Worker'),
        ('Admin', 'Admin'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    full_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='Engineer')
    department = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Profile"
        verbose_name_plural = "Profiles"

    def __str__(self):
        return f"Profile of {self.user.username}"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()


# ─────────────────────────────────────────────
# INVENTORY & MATERIALS
# ─────────────────────────────────────────────

class Category(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Material(models.Model):
    STATUS_CHOICES = [
        ('In Stock', 'In Stock'),
        ('Low Stock', 'Low Stock'),
        ('Out of Stock', 'Out of Stock'),
        ('On Order', 'On Order'),
    ]

    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    quantity_available = models.IntegerField(default=0)
    site_a_material_id = models.IntegerField(null=True, blank=True, unique=True)
    unit = models.CharField(max_length=50)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='In Stock')
    last_updated = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to='materials/', null=True, blank=True)

    code = models.CharField(max_length=50, unique=True, null=True, blank=True)
    description = models.TextField(blank=True)
    specifications = models.TextField(blank=True)       # ← merged from Stockpad2
    min_stock_level = models.IntegerField(default=10)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    supplier = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Material"
        verbose_name_plural = "Materials"
        ordering = ['name']
        indexes = [
            models.Index(fields=['category', 'status']),
            models.Index(fields=['code']),
            models.Index(fields=['quantity_available']),
        ]

    def __str__(self):
        return self.name

    @property
    def needs_reorder(self):
        return self.quantity_available <= self.min_stock_level

    @property
    def stock_value(self):
        return self.quantity_available * self.unit_cost


# ─────────────────────────────────────────────
# MATERIAL REQUESTS  (core — for engineers)
# ─────────────────────────────────────────────

class MaterialRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ]

    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='material_requests_made')
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='material_requests')
    quantity_needed = models.IntegerField()
    justification = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    request_date = models.DateTimeField(auto_now_add=True)
    site_a_request_id = models.IntegerField(null=True, blank=True, unique=True, db_index=True)
    sync_status = models.CharField(
        max_length=20,
        choices=[('not_synced', 'Not Synced'), ('synced', 'Synced'), ('sync_failed', 'Sync Failed')],
        default='not_synced',
    )

    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_requests_list')
    approved_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Material Request"
        verbose_name_plural = "Material Requests"
        ordering = ['-request_date']
        indexes = [
            models.Index(fields=['status', 'request_date']),
            models.Index(fields=['requested_by']),
            models.Index(fields=['material']),
        ]

    def __str__(self):
        return f"Request for {self.material.name} by {self.requested_by.username}"


# ─────────────────────────────────────────────
# BOM — Bill of Materials
# ─────────────────────────────────────────────

class Product(models.Model):
    CATEGORY_CHOICES = [
        ('residential', 'Residential'),
        ('commercial', 'Commercial'),
        ('industrial', 'Industrial'),
    ]

    id = models.CharField(max_length=20, primary_key=True)
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    version = models.CharField(max_length=10, default='1.0')
    estimated_cost_per_unit = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    production_time_days = models.IntegerField(validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['code']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def total_materials(self):
        return self.bom_items.filter(is_active=True).count()

    @property
    def calculated_cost(self):
        total = 0
        for item in self.bom_items.filter(is_active=True):
            total += float(item.quantity_per_unit) * float(item.material.unit_cost) * (1 + float(item.waste_factor))
        return total


class BOMItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='bom_items')
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    quantity_per_unit = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    waste_factor = models.DecimalField(max_digits=5, decimal_places=3, default=0.05, validators=[MinValueValidator(0)])
    category = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['product', 'material']
        ordering = ['category', 'material__name']

    def __str__(self):
        return f"{self.product.name} - {self.material.name}"

    @property
    def quantity_with_waste(self):
        return float(self.quantity_per_unit) * (1 + float(self.waste_factor))

    @property
    def total_cost_per_unit(self):
        return self.quantity_with_waste * float(self.material.unit_cost)


class ProductionPlan(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.CharField(max_length=20, primary_key=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} ({self.id})"

    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days


class ProductionPlanItem(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'), ('medium', 'Medium'), ('high', 'High'),
        ('urgent', 'Urgent'), ('critical', 'Critical'),
    ]

    plan = models.ForeignKey(ProductionPlan, on_delete=models.CASCADE, related_name='plan_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    start_week = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    duration_weeks = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    completed_quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['plan', 'product']
        ordering = ['priority', 'start_week']

    def __str__(self):
        return f"{self.plan.name} - {self.product.name} ({self.quantity} units)"

    @property
    def completion_percentage(self):
        if self.quantity == 0:
            return 0
        return (self.completed_quantity / self.quantity) * 100


class MaterialRequirement(models.Model):
    URGENCY_CHOICES = [
        ('low', 'Low'), ('medium', 'Medium'),
        ('high', 'High'), ('critical', 'Critical'),
    ]

    plan = models.ForeignKey(ProductionPlan, on_delete=models.CASCADE, related_name='requirements')
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    total_required = models.DecimalField(max_digits=12, decimal_places=2)
    current_stock = models.DecimalField(max_digits=12, decimal_places=2)
    shortage = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2)
    shortage_value = models.DecimalField(max_digits=12, decimal_places=2)
    urgency = models.CharField(max_length=10, choices=URGENCY_CHOICES)
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['plan', 'material']
        ordering = ['-shortage_value']

    def __str__(self):
        return f"{self.plan.name} - {self.material.name} (Shortage: {self.shortage})"


# ─────────────────────────────────────────────
# SUPPLIERS & PROCUREMENT
# ─────────────────────────────────────────────

class Supplier(models.Model):
    name = models.CharField(max_length=200, unique=True)
    contact_person = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    lead_time_days = models.IntegerField(default=7, validators=[MinValueValidator(0)])
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    reliability_score = models.DecimalField(max_digits=3, decimal_places=1, default=4.0, validators=[MinValueValidator(0)])
    specialties = models.TextField(default='', blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-reliability_score', 'name']

    def __str__(self):
        return f"{self.name} (Rating: {self.reliability_score})"

    @property
    def is_highly_reliable(self):
        return self.reliability_score >= 4.5


class ProcurementRequest(models.Model):
    """Procurement-level request (separate from engineer MaterialRequest)."""
    STATUS_CHOICES = [
        ('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved'),
        ('rejected', 'Rejected'), ('ordered', 'Ordered'),
        ('received', 'Received'), ('cancelled', 'Cancelled'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'), ('medium', 'Medium'), ('high', 'High'),
        ('urgent', 'Urgent'), ('critical', 'Critical'),
    ]

    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='procurement_requests')
    requested_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    current_stock = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    shortage_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='procurement_requests_made')
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='procurement_approvals')
    expected_delivery_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Procurement: {self.material.name} ({self.status})"


class ProcurementOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'), ('sent', 'Sent to Supplier'),
        ('confirmed', 'Confirmed by Supplier'), ('shipped', 'Shipped'),
        ('delivered', 'Delivered'), ('cancelled', 'Cancelled'),
    ]

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='orders')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    order_date = models.DateField()
    expected_delivery_date = models.DateField()
    actual_delivery_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    supplier_order_number = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-order_date']

    def __str__(self):
        return f"Order #{self.pk} - {self.supplier.name}"


class RequestStatusHistory(models.Model):
    """Audit trail for MaterialRequest status changes."""
    request = models.ForeignKey(MaterialRequest, on_delete=models.CASCADE, related_name='status_history')
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f"Request #{self.request.pk}: {self.old_status} → {self.new_status}"


# ─────────────────────────────────────────────
# CHATBOT HISTORY
# ─────────────────────────────────────────────

class ChatConversation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')
    title = models.CharField(max_length=255, default='New Chat')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Chat: {self.title} ({self.user.username})"

class ChatMessage(models.Model):
    conversation = models.ForeignKey(ChatConversation, on_delete=models.CASCADE, related_name='messages', null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    message = models.TextField()
    reply = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Message in {self.conversation or 'General'} by {self.user.username} at {self.timestamp}"
