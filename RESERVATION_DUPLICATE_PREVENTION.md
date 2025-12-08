# Inventory Reservation Duplicate Prevention

## Problem
When creating maintenance tasks with inventory requirements, duplicate reservations were being created because:
1. Frontend makes multiple API calls (one per inventory item)
2. No duplicate checking before creating reservations
3. User actions (refresh, retry) trigger the process again

## Solution: Three-Layer Protection

### 1. Backend Validation ✅ (IMPLEMENTED)
**File:** `app/services/inventory_service.py`

```python
async def create_inventory_reservation(self, reservation_data: Dict[str, Any], reserved_by: str):
    # Get item code (not document ID)
    item_code = item_data.get('item_code') or item_data.get('id') or inventory_id
    maintenance_task_id = reservation_data['maintenance_task_id']
    
    # Check if reservation already exists
    existing_reservations = await self.db.query_documents(
        COLLECTIONS['inventory_reservations'],
        [
            ('maintenance_task_id', '==', maintenance_task_id),
            ('inventory_id', '==', item_code),
            ('status', '==', 'reserved')
        ]
    )
    
    if existing_reservations:
        # Return existing reservation ID instead of creating duplicate
        return True, existing_reservations[0]['id'], None
    
    # Create new reservation only if none exists
    ...
```

**Benefits:**
- ✅ Prevents duplicates even if frontend makes multiple calls
- ✅ Idempotent - same call returns same result
- ✅ Always uses item_code, never document ID

### 2. Database Index 🔧 (NEEDS SETUP)
**File:** `app/database/collections.py`

```python
'inventory_reservations': {
    'compound_indexes': [
        {
            'fields': [
                ('inventory_id', 'ASCENDING'), 
                ('maintenance_task_id', 'ASCENDING'), 
                ('status', 'ASCENDING')
            ],
            'scope': 'COLLECTION'
        }
    ]
}
```

**Setup Required:**
Run the setup script:
```bash
python scripts/create_reservation_compound_index.py
```

Or manually create in Firebase Console:
1. Go to Firestore Database > Indexes
2. Create composite index with fields:
   - `inventory_id` (Ascending)
   - `maintenance_task_id` (Ascending)
   - `status` (Ascending)

**Benefits:**
- ✅ Makes duplicate-check queries extremely fast
- ✅ Ensures query performance doesn't degrade with scale
- ✅ Required for the backend duplicate check to work efficiently

### 3. Frontend Optimization 📱 (RECOMMENDED)
**What frontend should do:**

Before creating reservations:
```dart
// 1. Check if reservations already exist for this task
final existingReservations = await api.getInventoryReservations(
  maintenanceTaskId: taskId
);

// 2. Only create reservations for items that don't exist
for (final item in taskTypeItems) {
  final alreadyExists = existingReservations.any(
    (r) => r.inventoryId == item.id && r.status == 'reserved'
  );
  
  if (!alreadyExists) {
    await api.createInventoryReservation(...);
  }
}
```

**Benefits:**
- ✅ Reduces unnecessary API calls
- ✅ Faster UI response
- ✅ Less database load

## Current Status

| Layer | Status | Action Required |
|-------|--------|----------------|
| Backend Validation | ✅ Complete | None - already working |
| Database Index | ⚠️ Needs Setup | Run `scripts/create_reservation_compound_index.py` |
| Frontend Check | ❌ Not Implemented | Optional but recommended |

## Testing

After implementing all layers:

```bash
# 1. Create a maintenance task with inventory items
# 2. Refresh the page
# 3. Create the same task again
# Expected: No duplicate reservations created
# Expected: Same reservation IDs returned
```

## Migration

To clean up existing duplicates:

```python
# scripts/cleanup_duplicate_reservations.py
# TODO: Create script to:
# 1. Group reservations by (inventory_id, maintenance_task_id, status)
# 2. Keep the oldest reservation
# 3. Delete duplicates
# 4. Update maintenance task reservation_ids array
```
