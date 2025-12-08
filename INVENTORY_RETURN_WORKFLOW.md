# Inventory Return Workflow - Assessment Gated Returns

## Overview
This document describes the conditional auto-receive workflow for returning inventory items from maintenance tasks. The system now supports different handling based on item condition.

## Backend Changes

### 1. Updated `inventory_service.py` - `return_reservation` Method

**New Parameters:**
- `item_condition` (Optional[str]): "good" or "defective" - determines item destination
- `needs_replacement` (bool): Whether user wants a replacement for defective item

**Workflow Logic:**

#### Scenario A: Good Condition Return
```
IF item_condition == "good":
  1. Add quantity back to available stock immediately (+inventory count)
  2. Item status → "Available"
  3. Create return record with condition = "good"
  4. Return success
```

#### Scenario B: Defective/Broken Return
```
IF item_condition == "defective":
  1. Mark item status → "needs_repair"
  2. Set is_active = False (quarantine item)
  3. DO NOT add to available stock
  4. Send high-priority notification to all admins
  5. IF needs_replacement == True:
     - Create high-priority inventory request for replacement
  6. Create return record with condition = "defective"
  7. Return success with status = "quarantined"
```

### 2. Updated Inventory Router Endpoint

**Endpoint:** `POST /inventory/reservations/{reservation_id}/return`

**New Query Parameters:**
- `item_condition`: str (default: "good") - "good" or "defective"
- `needs_replacement`: bool (default: False)

**Response includes:**
```json
{
  "success": true,
  "message": "Reservation returned and stock updated",
  "data": {
    "return_id": "...",
    "reservation_id": "...",
    "inventory_id": "...",
    "quantity_returned": 5,
    "item_condition": "good|defective",
    "is_defective": false|true,
    "needs_replacement": false|true,
    "status": "available|quarantined",
    "new_stock": 25
  }
}
```

### 3. Updated `ReservationActionRequest` Model

**New Fields:**
```python
item_condition: Optional[str] = "good"  # "good" or "defective"
needs_replacement: bool = False
notes: Optional[str] = None
date_returned: Optional[datetime] = None
reservation_id: Optional[str] = None
```

**Endpoint:** `POST /inventory/reservations/action`

Can now handle returns with condition via the flexible action endpoint.

## Frontend Integration Required

### 1. Update `api_services_mobile.dart`

The `returnInventoryReservation` method needs to be updated:

```dart
/// Return inventory reservation with item condition
Future<Map<String, dynamic>> returnInventoryReservation(
  String reservationId, {
  int? quantity,
  String itemCondition = 'good',  // 'good' or 'defective'
  bool needsReplacement = false,
  String? notes,
  DateTime? dateReturned,
}) async {
  final token = await _requireToken();
  
  final queryParams = <String, String>{
    if (quantity != null) 'quantity': quantity.toString(),
    'item_condition': itemCondition,
    'needs_replacement': needsReplacement.toString(),
    if (notes != null && notes.isNotEmpty) 'notes': notes,
    if (dateReturned != null) 'date_returned': dateReturned.toIso8601String(),
  };
  
  final uri = Uri.parse('$baseUrl/inventory/reservations/$reservationId/return')
      .replace(queryParameters: queryParams);
  
  final response = await http.post(
    uri,
    headers: _authHeaders(token),
  );
  
  if (response.statusCode >= 200 && response.statusCode < 300) {
    return json.decode(response.body);
  } else {
    throw Exception('Failed to return reservation: ${response.body}');
  }
}
```

### 2. Update `handleReservationAction` Method

```dart
Future<Map<String, dynamic>> handleReservationAction({
  required String inventoryId,
  required int quantity,
  required String maintenanceTaskId,
  required String action, // "request" or "return"
  String? reservationId,
  String itemCondition = 'good',
  bool needsReplacement = false,
  String? notes,
  DateTime? dateReturned,
}) async {
  final token = await _requireToken();
  
  final body = {
    'inventory_id': inventoryId,
    'quantity': quantity,
    'maintenance_task_id': maintenanceTaskId,
    'action': action,
    'type': 'reservation',
    if (reservationId != null) 'reservation_id': reservationId,
    if (action == 'return') ...{
      'item_condition': itemCondition,
      'needs_replacement': needsReplacement,
      if (notes != null) 'notes': notes,
      if (dateReturned != null) 'date_returned': dateReturned.toIso8601String(),
    },
  };
  
  final response = await http.post(
    Uri.parse('$baseUrl/inventory/reservations/action'),
    headers: _authHeaders(token),
    body: json.encode(body),
  );
  
  if (response.statusCode >= 200 && response.statusCode < 300) {
    return json.decode(response.body);
  } else {
    throw Exception('Failed to handle reservation action: ${response.body}');
  }
}
```

### 3. Update `maintenance_detail.dart` Return Handler

In the `_handleInventoryAction` method, when `action == 'return'`:

```dart
} else if (action == 'return') {
  // Show return sheet to get condition
  final result = await showModalBottomSheet<ReturnResult>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (context) => ReturnItem(
      itemName: itemName,
      itemId: inventoryId,
      unit: unit,
      stock: currentStock.toString(),
      maintenanceId: widget.task['id'],
      staffName: currentUser.get("name") ?? "Unknown",
      requestId: requestId,
      requestedQuantity: request['quantity']?.toString(),
    ),
  );

  if (result != null) {
    try {
      // Parse condition from result.reason
      String itemCondition = 'good';
      if (result.reason.toLowerCase().contains('defective') || 
          result.reason.toLowerCase().contains('broken')) {
        itemCondition = 'defective';
      }
      
      // Call API with condition
      final response = await apiService.returnInventoryReservation(
        requestId,
        quantity: int.tryParse(result.quantity),
        itemCondition: itemCondition,
        needsReplacement: result.needsReplacement,
        notes: result.notes,
        dateReturned: result.dateReturned,
      );

      if (response['success'] == true) {
        final status = response['data']?['status'] ?? 'completed';
        final isQuarantined = status == 'quarantined';
        
        String message;
        if (isQuarantined) {
          message = 'Item returned and marked for repair. Admin has been notified.';
        } else {
          message = 'Item returned successfully and added to available stock.';
        }
        
        if (result.needsReplacement) {
          message += ' Replacement request created.';
        }
        
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(message)),
        );
        
        // Reload inventory
        await _loadInventoryRequests();
        
        // Trigger inventory refresh
        InventoryNotifier().notifyListeners();
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    }
  }
}
```

## User Workflow

### Scenario A: "I didn't need it" Return
1. Staff clicks "Return" on reserved item
2. Bottom sheet appears with ReturnItem form
3. Staff selects "Item Condition: Good / Not Needed"
4. Staff enters quantity and optional notes
5. Staff clicks "Submit"
6. **Backend Action:**
   - Item status → Available
   - Stock count +5 (or returned quantity)
   - Return record created
7. Success message: "Item returned successfully and added to available stock"
8. Staff can now complete assessment (if task complete)

### Scenario B: "I broke it" Return
1. Staff clicks "Return" on reserved item
2. Bottom sheet appears with ReturnItem form
3. Staff selects "Item Condition: Defective / Broken"
4. Staff checks "Need Replacement" (optional)
5. Staff enters notes: "Drill bit broke during AC repair"
6. Staff clicks "Submit"
7. **Backend Action:**
   - Item status → Needs Repair (quarantined)
   - Stock count unchanged (not added back)
   - Admin notification sent
   - If replacement requested: High-priority request created
8. Success message: "Item returned and marked for repair. Admin has been notified."
9. Staff can now complete assessment

## Database Schema Updates

### `inventory_returns` Collection
New fields tracked:
- `item_condition`: "good" | "defective"
- `is_defective`: boolean
- `needs_replacement`: boolean

### `inventory` Collection
New status value:
- `status`: "needs_repair" (in addition to existing statuses)
- `is_active`: False when needs_repair

### `inventory_requests` Collection
New field for tracking replacements:
- `replacement_for`: reservation_id (when created as replacement)
- `is_priority`: True for replacement requests

## Testing Checklist

- [ ] Return item in good condition → stock increases
- [ ] Return defective item → stock unchanged, status = needs_repair
- [ ] Defective item return sends admin notification
- [ ] Request replacement creates high-priority request
- [ ] Frontend displays correct status after return
- [ ] Assessment can be submitted after return
- [ ] Inventory notifier triggers list refresh

## API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/inventory/reservations/{id}/return` | POST | Return reservation with condition |
| `/inventory/reservations/action` | POST | Flexible action endpoint (request/return) |

Both endpoints now support the new `item_condition` and `needs_replacement` parameters for conditional auto-receive workflow.
