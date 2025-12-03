from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from ..database.database_service import database_service
from ..database.collections import COLLECTIONS
from app.services.user_id_service import UserIdService
from ..models.database_models import (
    Inventory, InventoryTransaction, InventoryRequest, InventoryReservation,
    LowStockAlert, InventoryUsageAnalytics
)
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

class InventoryService:
    """Comprehensive inventory management service"""
    
    def __init__(self):
        self.db = database_service
    
    # ═══════════════════════════════════════════════════════════════════════════
    # INVENTORY ITEM MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def create_inventory_item(self, item_data: Dict[str, Any], created_by: str) -> Tuple[bool, str, Optional[str]]:
        """Create a new inventory item"""
        try:
            # Add metadata
            item_data.update({
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'is_active': True
            })
            
            # Validate and create
            success, item_id, error = await self.db.create_document(
                COLLECTIONS['inventory'], 
                item_data,
                validate=True
            )
            
            if success:
                # Log the creation as a transaction
                await self._log_transaction(
                    inventory_id=item_id,
                    transaction_type="in",
                    quantity=item_data.get('current_stock', 0),
                    previous_stock=0,
                    new_stock=item_data.get('current_stock', 0),
                    performed_by=created_by,
                    reason="Initial stock creation"
                )
                
                # Check if item needs low stock alert
                await self._check_and_create_low_stock_alert(item_id, item_data)
                
                return True, item_id, None
            else:
                return False, f"Failed to create inventory item: {error}", error
                
        except Exception as e:
            error_msg = f"Error creating inventory item: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, error_msg
    
    async def get_inventory_item(self, item_id: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Get inventory item by ID"""
        try:
            # First try to find by custom ID field
            success, items, error = await self.db.query_documents(
                COLLECTIONS['inventory'],
                [('item_code', '==', item_id)]
            )
            
            if success and items:
                return True, items[0], None
            
            # Fallback to document ID
            return await self.db.get_document(COLLECTIONS['inventory'], item_id)
            
        except Exception as e:
            error_msg = f"Error getting inventory item {item_id}: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg
    
    async def update_inventory_item(self, item_id: str, update_data: Dict[str, Any], updated_by: str) -> Tuple[bool, Optional[str]]:
        """Update inventory item details (not stock levels)"""
        try:
            # Get current item
            success, current_item, error = await self.get_inventory_item(item_id)
            if not success:
                return False, f"Item not found: {error}"
            
            # Add metadata
            update_data['updated_at'] = datetime.now()
            
            # Update using document ID
            doc_id = current_item.get('_doc_id', item_id)
            success, error = await self.db.update_document(
                COLLECTIONS['inventory'], 
                doc_id, 
                update_data
            )
            
            if success:
                # If reorder level changed, check for alerts
                if 'reorder_level' in update_data:
                    await self._check_and_create_low_stock_alert(item_id, {**current_item, **update_data})
                
                return True, None
            else:
                return False, f"Failed to update inventory item: {error}"
                
        except Exception as e:
            error_msg = f"Error updating inventory item {item_id}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def deactivate_inventory_item(self, item_id: str, deactivated_by: str) -> Tuple[bool, Optional[str]]:
        """Deactivate an inventory item"""
        return await self.update_inventory_item(
            item_id, 
            {'is_active': False, 'deactivated_by': deactivated_by}, 
            deactivated_by
        )
    
    async def get_inventory_by_building(self, building_id: str, include_inactive: bool = False) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Get all inventory items for a building"""
        try:
            filters = [('building_id', '==', building_id)]
            if not include_inactive:
                filters.append(('is_active', '==', True))
            
            return await self.db.query_documents(COLLECTIONS['inventory'], filters)
            
        except Exception as e:
            error_msg = f"Error getting inventory for building {building_id}: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg
    
    async def get_all_inventory_items(self, include_inactive: bool = False) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Get all inventory items (no building filter)"""
        try:
            filters = []
        
            return await self.db.query_documents(COLLECTIONS['inventory'], filters)
            
        except Exception as e:
            error_msg = f"Error getting all inventory items: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg
    
    async def get_inventory_by_department(self, building_id: str, department: str) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Get inventory items by department"""
        try:
            filters = [
                ('building_id', '==', building_id),
                ('department', '==', department),
                ('is_active', '==', True)
            ]
            
            return await self.db.query_documents(COLLECTIONS['inventory'], filters)
            
        except Exception as e:
            error_msg = f"Error getting inventory for department {department}: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg
    
    async def search_inventory(self, building_id: str, search_term: str) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Search inventory items by name or code"""
        try:
            # Get all active inventory for building
            success, items, error = await self.get_inventory_by_building(building_id, include_inactive=False)
            
            if not success:
                return False, [], error
            
            # Filter by search term (case-insensitive)
            search_lower = search_term.lower()
            filtered_items = [
                item for item in items
                if (search_lower in item.get('item_name', '').lower() or
                    search_lower in item.get('item_code', '').lower() or
                    search_lower in item.get('description', '').lower())
            ]
            
            return True, filtered_items, None
            
        except Exception as e:
            error_msg = f"Error searching inventory: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STOCK MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def update_stock(self, item_id: str, quantity_change: int, transaction_type: str, 
                          performed_by: str, reference_type: str = None, reference_id: str = None, 
                          reason: str = None, cost_per_unit: float = None) -> Tuple[bool, Optional[str]]:
        """Update stock levels and log transaction"""
        try:
            # Get current item
            success, current_item, error = await self.get_inventory_item(item_id)
            if not success:
                return False, f"Item not found: {error}"
            
            current_stock = current_item.get('current_stock', 0)
            new_stock = current_stock + quantity_change
            
            # Validate stock levels
            if new_stock < 0:
                return False, f"Insufficient stock. Current: {current_stock}, Requested: {abs(quantity_change)}"
            
            # Update stock in database
            doc_id = current_item.get('_doc_id', item_id)
            update_success, update_error = await self.db.update_document(
                COLLECTIONS['inventory'],
                doc_id,
                {
                    'current_stock': new_stock,
                    'updated_at': datetime.now(),
                    'last_restocked_date': datetime.now() if quantity_change > 0 else current_item.get('last_restocked_date')
                }
            )
            
            if not update_success:
                return False, f"Failed to update stock: {update_error}"
            
            # Log transaction
            await self._log_transaction(
                inventory_id=item_id,
                transaction_type=transaction_type,
                quantity=abs(quantity_change),
                previous_stock=current_stock,
                new_stock=new_stock,
                performed_by=performed_by,
                reference_type=reference_type,
                reference_id=reference_id,
                reason=reason,
                cost_per_unit=cost_per_unit
            )
            
            # Check for low stock alerts
            updated_item = {**current_item, 'current_stock': new_stock}
            await self._check_and_create_low_stock_alert(item_id, updated_item)
            
            return True, None
            
        except Exception as e:
            error_msg = f"Error updating stock for item {item_id}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def consume_stock(self, item_id: str, quantity: int, performed_by: str, 
                           reference_type: str = None, reference_id: str = None, 
                           reason: str = None) -> Tuple[bool, Optional[str]]:
        """Consume stock (automatic deduction)"""
        return await self.update_stock(
            item_id=item_id,
            quantity_change=-quantity,
            transaction_type="out",
            performed_by=performed_by,
            reference_type=reference_type,
            reference_id=reference_id,
            reason=reason or "Stock consumption"
        )
    
    async def restock_item(self, item_id: str, quantity: int, performed_by: str, 
                          cost_per_unit: float = None, reason: str = None) -> Tuple[bool, Optional[str]]:
        """Add stock to inventory"""
        return await self.update_stock(
            item_id=item_id,
            quantity_change=quantity,
            transaction_type="in",
            performed_by=performed_by,
            reason=reason or "Stock replenishment",
            cost_per_unit=cost_per_unit
        )
    
    async def adjust_stock(self, item_id: str, new_quantity: int, performed_by: str, 
                          reason: str = None) -> Tuple[bool, Optional[str]]:
        """Adjust stock to specific quantity (for corrections)"""
        try:
            # Get current stock
            success, current_item, error = await self.get_inventory_item(item_id)
            if not success:
                return False, f"Item not found: {error}"
            
            current_stock = current_item.get('current_stock', 0)
            quantity_change = new_quantity - current_stock
            
            return await self.update_stock(
                item_id=item_id,
                quantity_change=quantity_change,
                transaction_type="adjustment",
                performed_by=performed_by,
                reason=reason or f"Stock adjustment from {current_stock} to {new_quantity}"
            )
            
        except Exception as e:
            error_msg = f"Error adjusting stock for item {item_id}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    # ═══════════════════════════════════════════════════════════════════════════
    # INVENTORY REQUESTS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def create_inventory_request(self, request_data: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        """Create an inventory request"""
        try:
            now = datetime.now()
            # Format date as YYYY-MM-DD for display consistency
            date_only = now.strftime('%Y-%m-%d')
            
            # Add metadata
            request_data.update({
                'created_at': now,
                'updated_at': now,
                'requested_date': now,
                'start_date': date_only,  # Add formatted date for display
                # Store maintenance_task_id if provided
                'maintenance_task_id': request_data.get('maintenance_task_id'),
                'reference_type': request_data.get('reference_type', 'maintenance_task'),
                'reference_id': request_data.get('reference_id') or request_data.get('maintenance_task_id')
            })
            
            success, request_id, error = await self.db.create_document(
                COLLECTIONS['inventory_requests'],
                request_data,
                validate=False  # Skip validation for now
            )

            if success:
                # Send FCM notification to admins
                try:
                    from ..services.fcm_service import fcm_service
                    full_request_data = {**request_data, 'id': request_id}
                    await fcm_service.send_inventory_request_notification(
                        full_request_data, "request_created"
                    )
                except Exception as fcm_error:
                    logger.warning(f"Failed to send FCM notification for new request: {str(fcm_error)}")

                # Notify admins/inventory staff via notification manager as well
                try:
                    from ..services.notification_manager import notification_manager
                    item_name = request_data.get('item_name') or ''
                    qty = request_data.get('quantity_requested', 1)
                    await notification_manager.notify_inventory_request_submitted(
                        request_id,
                        request_data.get('requested_by'),
                        item_name,
                        qty,
                        request_data.get('purpose', '')
                    )
                except Exception:
                    # Non-fatal
                    logger.debug("Failed to send inventory request submitted notifications via manager")
            
            return success, request_id, error
            
        except Exception as e:
            error_msg = f"Error creating inventory request: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, error_msg
    
    async def approve_inventory_request(self, request_id: str, approved_by: str, 
                                      quantity_approved: int = None, admin_notes: str = None) -> Tuple[bool, Optional[str]]:
        """Approve an inventory request"""
        try:
            # Get request
            success, request_data, error = await self.db.get_document(COLLECTIONS['inventory_requests'], request_id)
            if not success:
                return False, f"Request not found: {error}"
            
            if request_data.get('status') != 'pending':
                return False, f"Request is not pending (current status: {request_data.get('status')})"
            
            # Update request
            approved_quantity = quantity_approved or request_data.get('quantity_requested', 0)
            now = datetime.now()
            update_data = {
                'status': 'approved',
                'approved_by': approved_by,
                'quantity_approved': approved_quantity,
                'approved_date': now,
                'approved_date_formatted': now.strftime('%Y-%m-%d'),
                'updated_at': now
            }
            
            if admin_notes:
                update_data['admin_notes'] = admin_notes
            
            success, error = await self.db.update_document(COLLECTIONS['inventory_requests'], request_id, update_data, validate=False)
            
            if success:
                # Send FCM notification
                try:
                    from ..services.fcm_service import fcm_service
                    updated_request_data = {**request_data, **update_data}
                    await fcm_service.send_inventory_request_notification(
                        updated_request_data, "request_approved"
                    )
                except Exception as fcm_error:
                    logger.warning(f"Failed to send FCM notification for request approval: {str(fcm_error)}")

                # Automatically fulfill if stock is available
                await self._try_fulfill_request(request_id)
                return True, None
            else:
                return False, f"Failed to approve request: {error}"
                
        except Exception as e:
            error_msg = f"Error approving inventory request {request_id}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def deny_inventory_request(self, request_id: str, denied_by: str, admin_notes: str) -> Tuple[bool, Optional[str]]:
        """Deny an inventory request"""
        try:
            # Get request data for notification
            success, request_data, error = await self.db.get_document(COLLECTIONS['inventory_requests'], request_id)

            update_data = {
                'status': 'denied',
                'approved_by': denied_by,  # Using same field for tracking who made the decision
                'admin_notes': admin_notes,
                'approved_date': datetime.now(),  # When decision was made
                'updated_at': datetime.now()
            }
            
            success, error = await self.db.update_document(COLLECTIONS['inventory_requests'], request_id, update_data)
            
            if success:
                # Send FCM notification
                try:
                    from ..services.fcm_service import fcm_service
                    updated_request_data = {**request_data, **update_data}
                    await fcm_service.send_inventory_request_notification(
                        updated_request_data, "request_denied"
                    )
                except Exception as fcm_error:
                    logger.warning(f"Failed to send FCM notification for request denial: {str(fcm_error)}")
            
            return success, error

        except Exception as e:
            error_msg = f"Error denying inventory request {request_id}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def fulfill_inventory_request(self, request_id: str, fulfilled_by: str) -> Tuple[bool, Optional[str]]:
        """Fulfill an approved inventory request"""
        try:
            # Get request
            success, request_data, error = await self.db.get_document(COLLECTIONS['inventory_requests'], request_id)
            if not success:
                return False, f"Request not found: {error}"
            
            if request_data.get('status') != 'approved':
                return False, f"Request is not approved (current status: {request_data.get('status')})"
            
            # Consume stock
            inventory_id = request_data.get('inventory_id')
            quantity = request_data.get('quantity_approved', 0)
            
            consume_success, consume_error = await self.consume_stock(
                item_id=inventory_id,
                quantity=quantity,
                performed_by=fulfilled_by,
                reference_type="inventory_request",
                reference_id=request_id,
                reason=f"Fulfilled inventory request for {request_data.get('purpose', 'general use')}"
            )
            
            if not consume_success:
                return False, f"Failed to consume stock: {consume_error}"
            
            # Update request status
            update_data = {
                'status': 'fulfilled',
                'fulfilled_date': datetime.now(),
                'updated_at': datetime.now()
            }
            
            success, error = await self.db.update_document(COLLECTIONS['inventory_requests'], request_id, update_data, validate=False)
            return success, error
            
        except Exception as e:
            error_msg = f"Error fulfilling inventory request {request_id}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def get_inventory_requests(self, building_id: str = None, status: str = None,
                                   requested_by: str = None, maintenance_task_id: str = None) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Get inventory requests with filters"""
        try:
            filters = []

            if building_id:
                # Need to join with inventory to filter by building
                # For now, get all requests and filter in memory
                pass

            if status:
                filters.append(('status', '==', status))

            if requested_by:
                filters.append(('requested_by', '==', requested_by))

            if maintenance_task_id:
                filters.append(('maintenance_task_id', '==', maintenance_task_id))

            return await self.db.query_documents(COLLECTIONS['inventory_requests'], filters)

        except Exception as e:
            error_msg = f"Error getting inventory requests: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg

    async def get_inventory_request_by_id(self, request_id: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Get inventory request by ID"""
        try:
            success, request_data, error = await self.db.get_document(COLLECTIONS['inventory_requests'], request_id)

            if success and request_data:
                # Enrich with inventory item details
                inventory_id = request_data.get('inventory_id')
                if inventory_id:
                    item_success, item_data, _ = await self.get_inventory_item(inventory_id)
                    if item_success and item_data:
                        request_data['item_name'] = item_data.get('item_name')
                        request_data['item_code'] = item_data.get('item_code')
                        request_data['department'] = item_data.get('department')
                        request_data['current_stock'] = item_data.get('current_stock')
                        # Provide alias expected by frontend
                        request_data['available_stock'] = item_data.get('current_stock')
                        # Normalize quantity field for frontend
                        request_data['quantity'] = request_data.get('quantity_requested') or request_data.get('quantity_approved') or 1
                        request_data['requested_by'] = await UserIdService.get_user_full_name(request_data.get('requested_by'))
                return True, request_data, None
            else:
                return False, None, error

        except Exception as e:
            error_msg = f"Error getting inventory request {request_id}: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

    async def reserve_item_for_task(self, item_identifier: str, quantity: int, task_id: str, requested_by: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Attempt to reserve `quantity` of the given inventory item for a maintenance task.

        This tries to perform the reservation atomically using Firestore transactions when
        possible. It will create an `inventory_requests` document with status 'reserved'
        and mark the inventory item as reserved (reserved=True, reserved_for_task, reserved_quantity).

        Returns (success, request_id_or_error, error_str)
        """
        try:
            # Resolve inventory item
            item_success, item_data, item_err = await self.get_inventory_item(item_identifier)
            if not item_success or not item_data:
                return False, None, f"Inventory item not found: {item_err}"

            doc_id = item_data.get('_doc_id') or item_data.get('id') or item_identifier
            raw = None
            try:
                raw = self.db._raw_firestore()
            except Exception:
                raw = None

            request_id = uuid.uuid4().hex
            now = datetime.utcnow()
            request_payload = {
                'inventory_id': item_data.get('id') or doc_id,
                'item_name': item_data.get('item_name'),
                'item_code': item_data.get('item_code'),
                'available_stock': item_data.get('current_stock', 0),
                'quantity': quantity,
                'reserve': True,
                'requested_by': requested_by,
                'quantity_requested': quantity,
                'purpose': f"Reserved for maintenance task {task_id}",
                'maintenance_task_id': task_id,
                'reference_type': 'maintenance_task',
                'reference_id': task_id,
                'status': 'reserved',
                'tenant_can_request_again': True,
                'created_at': now,
                'updated_at': now,
                'requested_date': now,
                'start_date': now.strftime('%Y-%m-%d')
            }

            # Try to perform atomic reservation using Firestore transactions if available
            if raw is not None and hasattr(raw, 'transaction'):
                try:
                    # Import transactional decorator
                    from firebase_admin import firestore as admin_firestore

                    @admin_firestore.transactional
                    def _txn(transaction, inv_ref, req_ref, req_payload, qty_to_reserve):
                        snap = inv_ref.get(transaction=transaction)
                        inv = snap.to_dict() or {}
                        current_stock = inv.get('current_stock', 0)
                        reserved_qty = inv.get('reserved_quantity', 0) or 0
                        available = current_stock - reserved_qty
                        if available < qty_to_reserve:
                            raise Exception('Insufficient stock to reserve')

                        # Create request doc within transaction
                        transaction.set(req_ref, req_payload)

                        # Update inventory reserved flags and counters
                        new_reserved_qty = reserved_qty + qty_to_reserve
                        transaction.update(inv_ref, {
                            'reserved': True,
                            'reserved_for_task': task_id,
                            'reserved_at': now.isoformat(),
                            'reserved_quantity': new_reserved_qty,
                            'updated_at': now
                        })

                    inv_ref = raw.collection(COLLECTIONS['inventory']).document(doc_id)
                    req_ref = raw.collection(COLLECTIONS['inventory_requests']).document(request_id)
                    transaction = raw.transaction()
                    _txn(transaction, inv_ref, req_ref, request_payload, quantity)

                    # Transaction committed successfully; send non-critical notifications
                    try:
                        from ..services.fcm_service import fcm_service
                        await fcm_service.send_inventory_request_notification({**request_payload, 'id': request_id}, 'request_created')
                    except Exception:
                        logger.debug('FCM notification for reserved request failed')

                    try:
                        from ..services.notification_manager import notification_manager
                        item_name = item_data.get('item_name')
                        await notification_manager.notify_inventory_request_submitted(
                            request_id,
                            requested_by,
                            item_name,
                            quantity,
                            request_payload.get('purpose', '')
                        )
                        # If the related maintenance task has an assigned staff, notify them as well
                        try:
                            success_task, task_doc, err = await self.db.get_document(COLLECTIONS['maintenance_tasks'], task_id)
                            if success_task and task_doc:
                                assigned = task_doc.get('assigned_to')
                                if assigned:
                                    await notification_manager.notify_maintenance_task_assigned(
                                        task_id=task_id,
                                        staff_id=assigned,
                                        task_title=task_doc.get('task_title') or task_doc.get('title', ''),
                                        location=task_doc.get('location', ''),
                                        scheduled_date=task_doc.get('scheduled_date'),
                                        assigned_by=requested_by
                                    )
                        except Exception:
                            logger.debug('Failed to fetch task or notify assigned staff after reservation')
                    except Exception:
                        logger.debug('Notification manager failed for reserved request')

                    return True, request_id, None
                except Exception as e:
                    logger.debug(f'Atomic reservation transaction failed: {e}')
                    # fallthrough to non-transactional fallback

            # Fallback (non-transactional): best-effort reserve
            # Re-check availability
            success_check, current_item, err = await self.get_inventory_item(item_identifier)
            if not success_check:
                return False, None, f"Inventory item not found: {err}"
            current_stock = current_item.get('current_stock', 0)
            reserved_qty = current_item.get('reserved_quantity', 0) or 0
            available = current_stock - reserved_qty
            if available < quantity:
                return False, None, f"Insufficient stock to reserve (available {available})"

            # Create request document (non-atomic)
            success, rid, err = await self.create_inventory_request(request_payload)
            if not success:
                return False, None, f"Failed to create request: {err}"

            # Mark inventory as reserved (best-effort)
            try:
                await self.update_inventory_item(doc_id, {
                    'reserved': True,
                    'reserved_for_task': task_id,
                    'reserved_at': datetime.utcnow().isoformat(),
                    'reserved_quantity': reserved_qty + quantity
                }, requested_by)
            except Exception:
                logger.warning('Failed to mark inventory %s as reserved (non-atomic)', doc_id)

            return True, rid, None

        except Exception as e:
            logger.error(f"Error reserving inventory item {item_identifier}: {e}")
            return False, None, str(e)

    async def get_requests_by_maintenance_task(self, maintenance_task_id: str) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Get all inventory requests AND reservations linked to a maintenance task"""
        try:
            # Get inventory requests (traditional requests for new parts)
            success1, requests1, _ = await self.db.query_documents(
                COLLECTIONS['inventory_requests'],
                [('maintenance_task_id', '==', maintenance_task_id)]
            )

            success2, requests2, _ = await self.db.query_documents(
                COLLECTIONS['inventory_requests'],
                [('reference_id', '==', maintenance_task_id)]
            )

            # Get inventory reservations (parts reserved for this task)
            success3, reservations, _ = await self.db.query_documents(
                COLLECTIONS['inventory_reservations'],
                [('maintenance_task_id', '==', maintenance_task_id)]
            )

            # Combine and deduplicate results
            all_items = []
            seen_ids = set()

            # Add requests
            for items_list in [requests1, requests2]:
                if items_list:
                    for item in items_list:
                        item_id = item.get('_doc_id') or item.get('id')
                        if item_id and item_id not in seen_ids:
                            seen_ids.add(item_id)
                            # Mark as request type
                            item['_item_type'] = 'request'
                            all_items.append(item)

            # Add reservations
            if success3 and reservations:
                for reservation in reservations:
                    res_id = reservation.get('_doc_id') or reservation.get('id')
                    if res_id and res_id not in seen_ids:
                        seen_ids.add(res_id)
                        # Mark as reservation type
                        reservation['_item_type'] = 'reservation'
                        all_items.append(reservation)

            return True, all_items, None

        except Exception as e:
            error_msg = f"Error getting inventory items for maintenance task {maintenance_task_id}: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LOW STOCK ALERTS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_low_stock_alerts(self, building_id: str = None, status: str = "active") -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Get low stock alerts"""
        try:
            filters = []
            
            if building_id:
                filters.append(('building_id', '==', building_id))
            
            if status:
                filters.append(('status', '==', status))
            
            return await self.db.query_documents(COLLECTIONS['low_stock_alerts'], filters)
            
        except Exception as e:
            error_msg = f"Error getting low stock alerts: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg
    
    async def acknowledge_low_stock_alert(self, alert_id: str, acknowledged_by: str) -> Tuple[bool, Optional[str]]:
        """Acknowledge a low stock alert"""
        try:
            update_data = {
                'status': 'acknowledged',
                'acknowledged_by': acknowledged_by,
                'acknowledged_at': datetime.now()
            }
            
            return await self.db.update_document(COLLECTIONS['low_stock_alerts'], alert_id, update_data)
            
        except Exception as e:
            error_msg = f"Error acknowledging low stock alert {alert_id}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def resolve_low_stock_alert(self, alert_id: str) -> Tuple[bool, Optional[str]]:
        """Resolve a low stock alert (usually after restocking)"""
        try:
            update_data = {
                'status': 'resolved',
                'resolved_at': datetime.now()
            }
            
            return await self.db.update_document(COLLECTIONS['low_stock_alerts'], alert_id, update_data)
            
        except Exception as e:
            error_msg = f"Error resolving low stock alert {alert_id}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TRANSACTION HISTORY
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_inventory_transactions(self, inventory_id: str = None, transaction_type: str = None, 
                                       start_date: datetime = None, end_date: datetime = None) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Get inventory transaction history"""
        try:
            filters = []
            
            if inventory_id:
                filters.append(('inventory_id', '==', inventory_id))
            
            if transaction_type:
                filters.append(('transaction_type', '==', transaction_type))
            
            # Note: Date range filtering would need to be done in memory for Firestore
            # or use composite indexes
            
            return await self.db.query_documents(COLLECTIONS['inventory_transactions'], filters)
            
        except Exception as e:
            error_msg = f"Error getting inventory transactions: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg
    
    # ═══════════════════════════════════════════════════════════════════════════
    # USAGE ANALYTICS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def generate_usage_analytics(self, building_id: str, period_type: str = "monthly") -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Generate usage analytics for inventory items"""
        try:
            # This would typically be run as a background job
            # For now, return existing analytics
            filters = [
                ('building_id', '==', building_id),
                ('period_type', '==', period_type)
            ]
            
            return await self.db.query_documents(COLLECTIONS['inventory_usage_analytics'], filters)
            
        except Exception as e:
            error_msg = f"Error generating usage analytics: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg
    
    async def get_inventory_summary(self, building_id: str) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """Get inventory summary statistics"""
        try:
            # Get all inventory items
            success, items, error = await self.get_inventory_by_building(building_id)
            if not success:
                return False, {}, error
            
            # Calculate summary statistics
            total_items = len(items)
            low_stock_items = len([item for item in items if item.get('current_stock', 0) <= item.get('reorder_level', 0)])
            out_of_stock_items = len([item for item in items if item.get('current_stock', 0) == 0])
            critical_items = len([item for item in items if item.get('is_critical', False)])
            
            # Calculate total value (if cost data available)
            total_value = sum(
                item.get('current_stock', 0) * item.get('unit_cost', 0)
                for item in items
                if item.get('unit_cost')
            )
            
            summary = {
                'total_items': total_items,
                'low_stock_items': low_stock_items,
                'out_of_stock_items': out_of_stock_items,
                'critical_items': critical_items,
                'total_value': total_value,
                'items_by_department': {},
                'items_by_classification': {}
            }
            
            # Group by department and classification
            for item in items:
                dept = item.get('department', 'Unknown')
                classification = item.get('classification', 'Unknown')
                
                if dept not in summary['items_by_department']:
                    summary['items_by_department'][dept] = 0
                summary['items_by_department'][dept] += 1
                
                if classification not in summary['items_by_classification']:
                    summary['items_by_classification'][classification] = 0
                summary['items_by_classification'][classification] += 1
            
            return True, summary, None
            
        except Exception as e:
            error_msg = f"Error getting inventory summary: {str(e)}"
            logger.error(error_msg)
            return False, {}, error_msg
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIVATE HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _log_transaction(self, inventory_id: str, transaction_type: str, quantity: int,
                              previous_stock: int, new_stock: int, performed_by: str,
                              reference_type: str = None, reference_id: str = None,
                              reason: str = None, cost_per_unit: float = None) -> None:
        """Log an inventory transaction"""
        try:
            transaction_data = {
                'inventory_id': inventory_id,
                'transaction_type': transaction_type,
                'quantity': quantity,
                'previous_stock': previous_stock,
                'new_stock': new_stock,
                'performed_by': performed_by,
                'reference_type': reference_type,
                'reference_id': reference_id,
                'reason': reason,
                'cost_per_unit': cost_per_unit,
                'total_cost': cost_per_unit * quantity if cost_per_unit else None,
                'created_at': datetime.now()
            }
            
            await self.db.create_document(COLLECTIONS['inventory_transactions'], transaction_data)
            
        except Exception as e:
            logger.error(f"Failed to log transaction for inventory {inventory_id}: {str(e)}")
    
    async def _check_and_create_low_stock_alert(self, inventory_id: str, item_data: Dict[str, Any]) -> None:
        """Check if item needs low stock alert and create if necessary"""
        try:
            current_stock = item_data.get('current_stock', 0)
            reorder_level = item_data.get('reorder_level', 0)

            if current_stock <= reorder_level:
                # Determine alert level
                if current_stock == 0:
                    alert_level = "out_of_stock"
                elif current_stock <= reorder_level * 0.5:
                    alert_level = "critical"
                else:
                    alert_level = "low"

                # Check if alert already exists
                success, existing_alerts, _ = await self.db.query_documents(
                    COLLECTIONS['low_stock_alerts'],
                    [
                        ('inventory_id', '==', inventory_id),
                        ('status', '==', 'active')
                    ]
                )

                if not success or not existing_alerts:
                    # Create new alert
                    alert_data = {
                        'inventory_id': inventory_id,
                        'building_id': item_data.get('building_id'),
                        'item_name': item_data.get('item_name'),
                        'current_stock': current_stock,
                        'reorder_level': reorder_level,
                        'alert_level': alert_level,
                        'status': 'active',
                        'created_at': datetime.now()
                    }

                    await self.db.create_document(COLLECTIONS['low_stock_alerts'], alert_data)

                    # Send notification to admins
                    try:
                        from ..services.notification_manager import notification_manager
                        is_critical = alert_level in ["critical", "out_of_stock"] or item_data.get('is_critical', False)

                        await notification_manager.notify_inventory_low_stock(
                            inventory_id=inventory_id,
                            item_name=item_data.get('item_name', 'Unknown Item'),
                            current_stock=current_stock,
                            reorder_level=reorder_level,
                            building_id=item_data.get('building_id'),
                            department=item_data.get('department'),
                            is_critical=is_critical
                        )
                        logger.info(f"Sent low stock notification for item {item_data.get('item_name')}")
                    except Exception as notif_error:
                        logger.error(f"Failed to send low stock notification: {str(notif_error)}")
            else:
                # Stock is above reorder level, resolve any existing alerts
                success, existing_alerts, _ = await self.db.query_documents(
                    COLLECTIONS['low_stock_alerts'],
                    [
                        ('inventory_id', '==', inventory_id),
                        ('status', '==', 'active')
                    ]
                )

                if success and existing_alerts:
                    for alert in existing_alerts:
                        alert_id = alert.get('_doc_id')
                        if alert_id:
                            await self.resolve_low_stock_alert(alert_id)

        except Exception as e:
            logger.error(f"Failed to check low stock alert for inventory {inventory_id}: {str(e)}")
    
    async def _try_fulfill_request(self, request_id: str) -> None:
        """Try to automatically fulfill an approved request if stock is available"""
        try:
            # Get request
            success, request_data, _ = await self.db.get_document(COLLECTIONS['inventory_requests'], request_id)
            if not success or request_data.get('status') != 'approved':
                return
            
            # Check stock availability
            inventory_id = request_data.get('inventory_id')
            quantity_needed = request_data.get('quantity_approved', 0)
            
            item_success, item_data, _ = await self.get_inventory_item(inventory_id)
            if not item_success:
                return
            
            current_stock = item_data.get('current_stock', 0)
            
            # Auto-fulfill if stock is available
            if current_stock >= quantity_needed:
                await self.fulfill_inventory_request(request_id, "system_auto_fulfill")
                
        except Exception as e:
            logger.error(f"Failed to auto-fulfill request {request_id}: {str(e)}")

    async def update_inventory_request(self, request_id: str, update_data: Dict[str, Any], updated_by: str) -> Tuple[bool, Optional[str]]:
        """Update inventory request status and handle stock deduction"""
        try:
            # Get current request
            success, request_data, error = await self.db.get_document(COLLECTIONS['inventory_requests'], request_id)
            if not success:
                return False, error or "Request not found"
            
            new_status = update_data.get("status")
            deduct_stock = update_data.get("deduct_stock", False)
            
            # Update status
            update_data["updated_at"] = datetime.now()
            update_data["updated_by"] = updated_by 
            
            # Set timestamps based on status changes
            if new_status == "received":
                update_data["fulfilled_date"] = datetime.now()
            elif new_status == "approved":
                update_data["approved_date"] = datetime.now()
            
            # If status is 'received' and deduct_stock is True, deduct from inventory
            if new_status == "received" and deduct_stock:
                inventory_id = request_data.get("inventory_id")
                quantity = request_data.get("quantity_approved", request_data.get("quantity_requested", 0))
                
                # Get current item stock
                item_success, item_data, item_error = await self.get_inventory_item(inventory_id)
                if not item_success:
                    return False, f"Inventory item not found: {item_error}"
                
                current_stock = item_data.get("current_stock", 0)
                if current_stock < quantity:
                    return False, f"Insufficient stock: {current_stock} available, {quantity} needed"
                
                # Deduct stock
                new_stock = current_stock - quantity
                stock_update = {"current_stock": new_stock, "updated_at": datetime.now()}
                await self.db.update_document(COLLECTIONS['inventory'], inventory_id, stock_update)
                
                # Log transaction
                await self._log_transaction(
                    inventory_id=inventory_id,
                    transaction_type="out",
                    quantity=quantity,
                    previous_stock=current_stock,
                    new_stock=new_stock,
                    reference_type="inventory_request",
                    reference_id=request_id,
                    performed_by=updated_by
                )
            
            # Update the request
            success, error = await self.db.update_document(COLLECTIONS['inventory_requests'], request_id, update_data)
            return success, error
            
        except Exception as e:
            logger.error(f"Error updating inventory request {request_id}: {str(e)}")
            return False, str(e)

    async def patch_inventory_item(self, item_id: str, update_data: Dict[str, Any], updated_by: str) -> Tuple[bool, Optional[str]]:
        """Patch inventory item (e.g., update stock)"""
        try:
            update_data["updated_at"] = datetime.now()
            update_data["updated_by"] = updated_by
            
            success, error = await self.db.update_document(COLLECTIONS['inventory'], item_id, update_data)
            return success, error
            
        except Exception as e:
            logger.error(f"Error patching inventory item {item_id}: {str(e)}")
            return False, str(e)

    # ═══════════════════════════════════════════════════════════════════════════
    # INVENTORY REQUEST MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════

    async def create_inventory_request(self, request_data: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        """Create a new inventory request"""
        try:
            # Add metadata
            request_data.update({
                'status': 'pending',
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            })
            
            # Validate and create
            success, request_id, error = await self.db.create_document(
                COLLECTIONS['inventory_requests'], 
                request_data,
                validate=True
            )
            
            if success:
                logger.info(f"Inventory request created: {request_id}")
            
            return success, request_id, error
            
        except Exception as e:
            logger.error(f"Error creating inventory request: {str(e)}")
            return False, "", str(e)

    async def get_inventory_requests(self, building_id: Optional[str] = None, status: Optional[str] = None, 
                                   requested_by: Optional[str] = None, maintenance_task_id: Optional[str] = None) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Get inventory requests with optional filters"""
        try:
            filters = []
            
            if building_id:
                filters.append(('building_id', '==', building_id))
            
            if status:
                filters.append(('status', '==', status))
            
            if requested_by:
                filters.append(('requested_by', '==', requested_by))
            
            if maintenance_task_id:
                filters.append(('maintenance_task_id', '==', maintenance_task_id))
            
            success, requests, error = await self.db.query_documents(COLLECTIONS['inventory_requests'], filters)
            return success, requests, error
            
        except Exception as e:
            logger.error(f"Error getting inventory requests: {str(e)}")
            return False, [], str(e)

    async def get_inventory_request_by_id(self, request_id: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Get inventory request by ID"""
        try:
            success, request_data, error = await self.db.get_document(COLLECTIONS['inventory_requests'], request_id)
            return success, request_data, error
            
        except Exception as e:
            logger.error(f"Error getting inventory request {request_id}: {str(e)}")
            return False, None, str(e)

    async def fulfill_inventory_request(self, request_id: str, fulfilled_by: str) -> Tuple[bool, Optional[str]]:
        """Mark inventory request as fulfilled"""
        try:
            update_data = {
                'status': 'fulfilled',
                'fulfilled_by': fulfilled_by,
                'fulfilled_at': datetime.now(),
                'updated_at': datetime.now()
            }
            
            success, error = await self.db.update_document(COLLECTIONS['inventory_requests'], request_id, update_data)
            return success, error
            
        except Exception as e:
            logger.error(f"Error fulfilling inventory request {request_id}: {str(e)}")
            return False, str(e)

    async def approve_inventory_request(self, request_id: str, approved_by: str, quantity_approved: Optional[int] = None, admin_notes: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Approve an inventory request"""
        try:
            # Get current request
            success, request_data, error = await self.db.get_document(COLLECTIONS['inventory_requests'], request_id)
            if not success:
                return False, error or "Request not found"
            
            update_data = {
                'status': 'approved',
                'approved_by': approved_by,
                'approved_date': datetime.now(),
                'quantity_approved': quantity_approved or request_data.get('quantity_requested', 0),
                'admin_notes': admin_notes,
                'updated_at': datetime.now()
            }
            
            success, error = await self.db.update_document(COLLECTIONS['inventory_requests'], request_id, update_data)
            return success, error
            
        except Exception as e:
            logger.error(f"Error approving inventory request {request_id}: {str(e)}")
            return False, str(e)

    async def deny_inventory_request(self, request_id: str, denied_by: str, admin_notes: str) -> Tuple[bool, Optional[str]]:
        """Deny an inventory request"""
        try:
            update_data = {
                'status': 'denied',
                'approved_by': denied_by,  # Using approved_by field for consistency
                'approved_date': datetime.now(),
                'admin_notes': admin_notes,
                'updated_at': datetime.now()
            }
            
            success, error = await self.db.update_document(COLLECTIONS['inventory_requests'], request_id, update_data)
            return success, error
            
        except Exception as e:
            logger.error(f"Error denying inventory request {request_id}: {str(e)}")
            return False, str(e)

    async def consume_stock(self, item_id: str, quantity: int, performed_by: str, reference_type: Optional[str] = None, reference_id: Optional[str] = None, reason: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Consume stock from inventory"""
        try:
            # Get current item
            success, item_data, error = await self.get_inventory_item(item_id)
            if not success:
                return False, error or "Item not found"
            
            current_stock = item_data.get('current_stock', 0)
            if current_stock < quantity:
                return False, f"Insufficient stock: {current_stock} available, {quantity} needed"
            
            # Update stock
            new_stock = current_stock - quantity
            update_data = {
                'current_stock': new_stock,
                'updated_at': datetime.now()
            }
            
            success, error = await self.db.update_document(COLLECTIONS['inventory'], item_id, update_data)
            if not success:
                return False, error
            
            # Log transaction
            await self._log_transaction(
                inventory_id=item_id,
                transaction_type="out",
                quantity=quantity,
                previous_stock=current_stock,
                new_stock=new_stock,
                performed_by=performed_by,
                reference_type=reference_type,
                reference_id=reference_id,
                reason=reason
            )
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error consuming stock for item {item_id}: {str(e)}")
            return False, str(e)

    async def restock_item(self, item_id: str, quantity: int, performed_by: str, cost_per_unit: Optional[float] = None, reason: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Add stock to inventory"""
        try:
            # Get current item
            success, item_data, error = await self.get_inventory_item(item_id)
            if not success:
                return False, error or "Item not found"
            
            current_stock = item_data.get('current_stock', 0)
            new_stock = current_stock + quantity
            
            # Update stock
            update_data = {
                'current_stock': new_stock,
                'updated_at': datetime.now()
            }
            
            success, error = await self.db.update_document(COLLECTIONS['inventory'], item_id, update_data)
            if not success:
                return False, error
            
            # Log transaction
            await self._log_transaction(
                inventory_id=item_id,
                transaction_type="in",
                quantity=quantity,
                previous_stock=current_stock,
                new_stock=new_stock,
                performed_by=performed_by,
                reason=reason,
                cost_per_unit=cost_per_unit
            )
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error restocking item {item_id}: {str(e)}")
            return False, str(e)

    async def adjust_stock(self, item_id: str, new_quantity: int, performed_by: str, reason: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Adjust stock to specific quantity"""
        try:
            # Get current item
            success, item_data, error = await self.get_inventory_item(item_id)
            if not success:
                return False, error or "Item not found"
            
            current_stock = item_data.get('current_stock', 0)
            quantity_change = new_quantity - current_stock
            
            # Update stock
            update_data = {
                'current_stock': new_quantity,
                'updated_at': datetime.now()
            }
            
            success, error = await self.db.update_document(COLLECTIONS['inventory'], item_id, update_data)
            if not success:
                return False, error
            
            # Log transaction (adjustment)
            transaction_type = "in" if quantity_change > 0 else "out"
            await self._log_transaction(
                inventory_id=item_id,
                transaction_type="adjustment",
                quantity=abs(quantity_change),
                previous_stock=current_stock,
                new_stock=new_quantity,
                performed_by=performed_by,
                reason=reason
            )
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error adjusting stock for item {item_id}: {str(e)}")
            return False, str(e)

    async def get_low_stock_alerts(self, building_id: Optional[str] = None, status: str = "active") -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Get low stock alerts with optional filters"""
        try:
            filters = [('status', '==', status)]
            if building_id:
                filters.append(('building_id', '==', building_id))
            
            success, alerts, error = await self.db.query_documents(COLLECTIONS['low_stock_alerts'], filters)
            return success, alerts, error
            
        except Exception as e:
            logger.error(f"Error getting low stock alerts: {str(e)}")
            return False, [], str(e)

    async def acknowledge_low_stock_alert(self, alert_id: str, acknowledged_by: str) -> Tuple[bool, Optional[str]]:
        """Acknowledge a low stock alert"""
        try:
            update_data = {
                'status': 'acknowledged',
                'acknowledged_by': acknowledged_by,
                'acknowledged_at': datetime.now()
            }
            
            success, error = await self.db.update_document(COLLECTIONS['low_stock_alerts'], alert_id, update_data)
            return success, error
            
        except Exception as e:
            logger.error(f"Error acknowledging low stock alert {alert_id}: {str(e)}")
            return False, str(e)

    async def create_inventory_reservation(self, reservation_data: Dict[str, Any], reserved_by: str) -> Tuple[bool, str, Optional[str]]:
        """Create a new inventory reservation for maintenance tasks"""
        try:
            # Validate quantity
            if not reservation_data.get('quantity') or reservation_data['quantity'] <= 0:
                return False, None, "Quantity must be greater than 0"
            
            # Get current stock level for the inventory item
            inventory_id = reservation_data['inventory_id']
            success, item_data, error = await self.get_inventory_item(inventory_id)
            if not success or not item_data:
                return False, None, f"Inventory item not found: {inventory_id}"
            
            current_stock = item_data.get('current_stock', 0)
            
            # Prepare data with correct fields
            data = {
                'inventory_id': inventory_id,  # Should be item code from frontend
                'created_by': reserved_by,
                'maintenance_task_id': reservation_data['maintenance_task_id'],
                'quantity': reservation_data['quantity'],  # Use 'quantity'
                'current_stock': current_stock,  # Add current stock at time of reservation
                'purpose': 'maintenance',
                'status': 'reserved',
                'reserved_at': datetime.utcnow(),
                'created_at': datetime.utcnow(),
            }
            
            # Validate and create
            success, reservation_id, error = await self.db.create_document(
                COLLECTIONS['inventory_reservations'], 
                data,
                validate=True
            )
            
            if success:
                logger.info(f"Inventory reservation created: {reservation_id}")
            
            return success, reservation_id, error
            
        except Exception as e:
            logger.error(f"Error creating inventory reservation: {str(e)}")
            return False, "", str(e)

    async def get_inventory_reservations(self, filters: Optional[Dict[str, Any]] = None) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Get inventory reservations with optional filters"""
        try:
            query = []
            if filters:
                if 'maintenance_task_id' in filters:
                    query.append(('maintenance_task_id', '==', filters['maintenance_task_id']))
            
            success, documents, error = await self.db.query_documents(
                COLLECTIONS['inventory_reservations'],
                query
            )
            
            if success:
                # Map documents to correct field format
                reservations = []
                for doc in documents:
                    reservations.append({
                        'inventory_id': doc.get('inventory_id'),  # Item code
                        'quantity': doc.get('quantity') or doc.get('quantity_reserved'),  # Handle both old and new field names
                        'current_stock': doc.get('current_stock', 0),  # Stock level at time of reservation
                        'maintenance_task_id': doc.get('maintenance_task_id'),
                        'created_at': doc.get('reserved_at') or doc.get('created_at'),
                        'status': doc.get('status', 'reserved'),
                    })
                return True, reservations, None
            else:
                return success, [], error
                
        except Exception as e:
            logger.error(f"Error getting inventory reservations: {str(e)}")
            return False, [], str(e)

    async def get_inventory_reservation_by_id(self, reservation_id: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Get a single inventory reservation by document id"""
        try:
            return await self.db.get_document(COLLECTIONS['inventory_reservations'], reservation_id)
        except Exception as e:
            logger.error(f"Error getting reservation {reservation_id}: {e}")
            return False, None, str(e)

    async def update_reservation_status(self, reservation_id: str, new_status: str, updated_by: str) -> Tuple[bool, Optional[str]]:
        """Update inventory reservation status"""
        try:
            # Validate status
            valid_statuses = ['reserved', 'received', 'consumed', 'released']
            if new_status not in valid_statuses:
                return False, f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            
            # Get current reservation
            success, reservation_data, error = await self.db.get_document(COLLECTIONS['inventory_reservations'], reservation_id)
            if not success:
                return False, f"Reservation not found: {error}"
            
            current_status = reservation_data.get('status')
            if current_status == new_status:
                return False, f"Reservation is already {new_status}"
            
            # Prepare update data
            update_data = {
                'status': new_status,
                'updated_at': datetime.utcnow()
            }
            
            # Add timestamp based on status
            if new_status == 'received':
                update_data['received_at'] = datetime.utcnow()
            elif new_status == 'consumed':
                update_data['consumed_at'] = datetime.utcnow()
            elif new_status == 'released':
                update_data['released_at'] = datetime.utcnow()
            
            # Update reservation
            success, error = await self.db.update_document(COLLECTIONS['inventory_reservations'], reservation_id, update_data)
            
            if success:
                # Handle status-specific logic
                if new_status == 'released' and current_status == 'reserved':
                    # When releasing a reservation, restore the reserved quantity
                    inventory_id = reservation_data.get('inventory_id')
                    quantity = reservation_data.get('quantity', 0)
                    
                    if inventory_id and quantity > 0:
                        try:
                            # Get current inventory item
                            item_success, item_data, _ = await self.get_inventory_item(inventory_id)
                            if item_success and item_data:
                                doc_id = item_data.get('_doc_id', inventory_id)
                                current_reserved = item_data.get('reserved_quantity', 0)
                                new_reserved = max(0, current_reserved - quantity)
                                
                                await self.update_inventory_item(doc_id, {
                                    'reserved_quantity': new_reserved
                                }, updated_by)
                        except Exception as update_error:
                            logger.warning(f"Failed to update reserved quantity for released reservation: {update_error}")
                
                elif new_status == 'received' and current_status == 'reserved':
                    # When marking as received, deduct from actual stock and log transaction
                    inventory_id = reservation_data.get('inventory_id')
                    quantity = reservation_data.get('quantity', 0)
                    maintenance_task_id = reservation_data.get('maintenance_task_id')
                    
                    if inventory_id and quantity > 0:
                        try:
                            # Deduct from current stock and log transaction
                            stock_success, stock_error = await self.update_stock(
                                item_id=inventory_id,
                                quantity_change=-quantity,  # Negative for deduction
                                transaction_type='out',
                                performed_by=updated_by,
                                reference_type='maintenance_task',
                                reference_id=maintenance_task_id,
                                reason=f'Items issued for maintenance task {maintenance_task_id}'
                            )
                            
                            if not stock_success:
                                logger.error(f"Failed to deduct stock for received reservation {reservation_id}: {stock_error}")
                                # Note: We don't fail the reservation update if stock deduction fails
                                # This prevents blocking the workflow due to stock issues
                            
                        except Exception as deduction_error:
                            logger.error(f"Error deducting stock for received reservation {reservation_id}: {deduction_error}")
                
                logger.info(f"Reservation {reservation_id} status updated to {new_status}")
                return True, None
            else:
                return False, f"Failed to update reservation: {error}"
                
        except Exception as e:
            error_msg = f"Error updating reservation {reservation_id} status: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    async def mark_reservation_consumed(self, reservation_id: str, consumed_by: str) -> Tuple[bool, Optional[str]]:
        """Mark reservation as consumed (items used for completed task)"""
        return await self.update_reservation_status(reservation_id, 'consumed', consumed_by)

    async def release_reservation(self, reservation_id: str, released_by: str) -> Tuple[bool, Optional[str]]:
        """Release reservation (cancel reservation)"""
        return await self.update_reservation_status(reservation_id, 'released', released_by)

    async def mark_reservation_received(self, reservation_id: str, received_by: str) -> Tuple[bool, Optional[str]]:
        """Mark reservation as received (staff has picked up the items)"""
        return await self.update_reservation_status(reservation_id, 'received', received_by)

    async def mark_task_inventory_received(self, task_id: str, received_by: str, deduct_stock: bool = True) -> Tuple[bool, Optional[str]]:
        """Mark all inventory requests/reservations associated with a maintenance task as received.

        This will iterate over inventory_requests with maintenance_task_id==task_id and update
        them to 'received'. For reservations, it will mark as received and deduct stock.
        """
        try:
            # Handle inventory requests (created via reserve_item_for_task)
            success, requests, error = await self.get_inventory_requests(maintenance_task_id=task_id)
            if not success:
                return False, error or "Failed to fetch inventory requests for task"

            # Update each request to received; optionally deduct stock
            for req in requests:
                req_id = req.get('_doc_id') or req.get('id')
                if not req_id:
                    continue
                update_data = {'status': 'received', 'deduct_stock': deduct_stock}
                await self.update_inventory_request(req_id, update_data, received_by)

            # Handle inventory reservations for tasks
            success_r, reservations, err_r = await self.get_inventory_reservations({'maintenance_task_id': task_id})
            if success_r and reservations:
                for res in reservations:
                    # Fetch reservation id (doc id not included in reservation view), attempt to find doc id using query
                    # Query for reservation document with same fields
                    # We'll attempt to match by maintenance_task_id + inventory_id + created_at
                    # As a fallback, if 'id' present, use that
                    reservation_id = None
                    reservation_id = res.get('id') or res.get('_doc_id')
                    if not reservation_id:
                        # Query to find doc id using maintenance_task_id and inventory_id and status 'reserved'
                        filters = [
                            ('maintenance_task_id', '==', task_id),
                            ('inventory_id', '==', res.get('inventory_id')),
                            ('status', '==', 'reserved')
                        ]
                        q_success, docs, q_err = await self.db.query_documents(COLLECTIONS['inventory_reservations'], filters)
                        if q_success and docs:
                            reservation_id = docs[0].get('_doc_id') or docs[0].get('id')
                    if not reservation_id:
                        continue
                    # Mark reservation as received
                    await self.mark_reservation_received(reservation_id, received_by)

            return True, None
        except Exception as e:
            logger.error(f"Error marking task {task_id} inventory received: {str(e)}")
            return False, str(e)

    async def return_inventory_request(self, request_id: str, returned_by: str, quantity: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        """Return items for a fulfilled request back to inventory."""
        try:
            success, request_data, error = await self.get_inventory_request_by_id(request_id)
            if not success or not request_data:
                return False, f"Request not found: {error}"

            inventory_id = request_data.get('inventory_id')
            qty = int(quantity or request_data.get('quantity_approved') or request_data.get('quantity_requested') or 0)
            if qty <= 0:
                return False, "Invalid quantity to return"

            # Restock the inventory
            restock_success, restock_err = await self.restock_item(inventory_id, qty, returned_by, reason=f"Return from request {request_id}")
            if not restock_success:
                return False, f"Failed to restock item: {restock_err}"

            # Update request status to 'returned'
            update_data = {
                'status': 'returned',
                'returned_by': returned_by,
                'returned_date': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            success_u, err_u = await self.db.update_document(COLLECTIONS['inventory_requests'], request_id, update_data, validate=False)
            return success_u, err_u
        except Exception as e:
            logger.error(f"Error returning inventory for request {request_id}: {str(e)}")
            return False, str(e)

    async def return_reservation(self, reservation_id: str, returned_by: str, quantity: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        """Return items for a reservation back to inventory and mark reservation released/returned"""
        try:
            success, reservation_data, error = await self.db.get_document(COLLECTIONS['inventory_reservations'], reservation_id)
            if not success or not reservation_data:
                return False, f"Reservation not found: {error}"

            inventory_id = reservation_data.get('inventory_id')
            qty = int(quantity or reservation_data.get('quantity', 0))
            if qty <= 0:
                return False, "Invalid quantity to return"

            # Restock the inventory
            restock_success, restock_err = await self.restock_item(inventory_id, qty, returned_by, reason=f"Return from reservation {reservation_id}")
            if not restock_success:
                return False, f"Failed to restock item: {restock_err}"

            # Update reservation to 'released' (or 'returned' if needed), and restore reserved_quantity variance
            # Decrease reserved_quantity if present
            try:
                item_success, item_data, item_err = await self.get_inventory_item(inventory_id)
                if item_success and item_data:
                    doc_id = item_data.get('_doc_id', inventory_id)
                    current_reserved = item_data.get('reserved_quantity', 0) or 0
                    new_reserved = max(0, current_reserved - qty)
                    await self.update_inventory_item(doc_id, {'reserved_quantity': new_reserved, 'updated_at': datetime.utcnow()}, returned_by)
            except Exception:
                logger.debug('Failed to adjust reserved_quantity on inventory item after return')

            # Update reservation to 'released' and set returned timestamp
            update_data = {
                'status': 'released',
                'released_at': datetime.utcnow(),
                'released_by': returned_by,
                'updated_at': datetime.utcnow()
            }
            success_u, err_u = await self.db.update_document(COLLECTIONS['inventory_reservations'], reservation_id, update_data)
            return success_u, err_u
        except Exception as e:
            logger.error(f"Error returning reservation {reservation_id}: {str(e)}")
            return False, str(e)

    async def request_replacement_for_defective_item(self, reservation_id: str, replacement_data: Dict[str, Any], requested_by: str) -> Tuple[bool, str, Optional[str]]:
        """Request replacement for a defective reserved item"""
        try:
            # Get the original reservation
            success, reservation_data, error = await self.db.get_document(COLLECTIONS['inventory_reservations'], reservation_id)
            if not success:
                return False, "", f"Reservation not found: {error}"

            # Check if reservation is in received status (staff has picked it up)
            if reservation_data.get('status') != 'received':
                return False, "", "Can only request replacement for received items"

            # Get inventory item details
            inventory_id = reservation_data.get('inventory_id')
            item_success, item_data, item_error = await self.get_inventory_item(inventory_id)
            if not item_success:
                return False, "", f"Inventory item not found: {item_error}"

            # Create replacement request
            quantity_needed = replacement_data.get('quantity_needed') or reservation_data.get('quantity', 1)
            reason = replacement_data.get('reason', 'Item found defective during inspection')

            request_data = {
                'inventory_id': inventory_id,
                'item_name': item_data.get('item_name', ''),
                'item_code': item_data.get('item_code', ''),
                'quantity_requested': quantity_needed,
                'purpose': f"Replacement for defective item - {reason}",
                'maintenance_task_id': reservation_data.get('maintenance_task_id'),
                'reference_type': 'maintenance_task',
                'reference_id': reservation_data.get('maintenance_task_id'),
                'requested_by': requested_by,
                'status': 'pending',
                'defective_reservation_id': reservation_id,  # Link to original reservation
                'replacement_reason': reason
            }

            # Create the request
            success, request_id, error = await self.create_inventory_request(request_data)

            if success:
                # Update the original reservation with defective note
                update_data = {
                    'is_defective': True,
                    'defective_reason': reason,
                    'replacement_requested': True,
                    'replacement_request_id': request_id,
                    'updated_at': datetime.utcnow()
                }

                await self.db.update_document(COLLECTIONS['inventory_reservations'], reservation_id, update_data)

                # Send notification
                try:
                    from ..services.notification_manager import notification_manager
                    await notification_manager.notify_inventory_replacement_requested(
                        request_id,
                        item_data.get('item_name', 'Unknown Item'),
                        quantity_needed,
                        reason,
                        reservation_data.get('maintenance_task_id')
                    )
                except Exception as notif_error:
                    logger.warning(f"Failed to send replacement request notification: {notif_error}")

                logger.info(f"Replacement request created for defective reservation {reservation_id}: {request_id}")
                return True, request_id, None
            else:
                return False, "", f"Failed to create replacement request: {error}"

        except Exception as e:
            error_msg = f"Error requesting replacement for reservation {reservation_id}: {str(e)}"
            logger.error(error_msg)
            return False, "", error_msg

    # ═══════════════════════════════════════════════════════════════════════════
    # FORECASTING METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    async def get_inventory_forecasting_data(self, building_id: str) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Get inventory forecasting data for all active items in a building"""
        try:
            # Get all active inventory items
            success, items, error = await self.get_inventory_by_building(building_id, include_inactive=False)
            if not success:
                return False, [], error

            forecasting_data = []

            for item in items:
                item_id = item['id']
                
                # Calculate monthly usage
                monthly_usage = await self._calculate_monthly_usage(item_id)
                
                # Calculate trend
                trend = await self._calculate_usage_trend(item_id)
                
                # Calculate days to minimum stock
                days_to_min = await self._calculate_days_to_minimum(item, monthly_usage)
                
                # Calculate reorder date
                reorder_date = await self._calculate_reorder_date(item, monthly_usage)
                
                # Format stock display
                current_stock = item.get('current_stock', 0)
                max_stock = item.get('max_stock_level', current_stock)
                stock_display = f"{current_stock}/{max_stock}"
                
                # Determine status
                status = "Active" if item.get('is_active', True) else "Inactive"
                
                forecasting_item = {
                    'id': item_id,
                    'name': item.get('item_name', ''),
                    'category': item.get('category', 'General'),
                    'status': status,
                    'stock': stock_display,
                    'usage': f"{monthly_usage:.1f}",
                    'trend': trend,
                    'daysToMin': days_to_min,
                    'reorderBy': reorder_date
                }
                
                forecasting_data.append(forecasting_item)
            
            return True, forecasting_data, None
            
        except Exception as e:
            error_msg = f"Error getting forecasting data: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg

    async def _calculate_monthly_usage(self, item_id: str) -> float:
        """Calculate average monthly usage for the last 3 months"""
        try:
            # Get transactions for the last 90 days
            ninety_days_ago = datetime.now() - timedelta(days=90)
            
            filters = [
                ('inventory_id', '==', item_id),
                ('transaction_type', '==', 'out'),
                ('created_at', '>=', ninety_days_ago)
            ]
            
            success, transactions, error = await self.db.query_documents(COLLECTIONS['inventory_transactions'], filters)
            
            if not success or not transactions:
                return 0.0
            
            # Calculate total consumed in 90 days
            total_consumed = sum(abs(t.get('quantity', 0)) for t in transactions)
            
            # Convert to monthly average
            monthly_usage = (total_consumed / 90) * 30
            
            return monthly_usage
            
        except Exception as e:
            logger.error(f"Error calculating monthly usage for {item_id}: {str(e)}")
            return 0.0

    async def _calculate_usage_trend(self, item_id: str) -> Dict[str, Any]:
        """Calculate usage trend (increasing, decreasing, stable)"""
        try:
            # Get current month usage
            current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            current_month_end = (current_month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            # Get previous month usage
            prev_month_end = current_month_start - timedelta(days=1)
            prev_month_start = prev_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Current month transactions
            current_filters = [
                ('inventory_id', '==', item_id),
                ('transaction_type', '==', 'out'),
                ('created_at', '>=', current_month_start),
                ('created_at', '<=', current_month_end)
            ]
            
            success_current, current_transactions, _ = await self.db.query_documents(COLLECTIONS['inventory_transactions'], current_filters)
            current_usage = sum(abs(t.get('quantity', 0)) for t in current_transactions) if success_current else 0
            
            # Previous month transactions
            prev_filters = [
                ('inventory_id', '==', item_id),
                ('transaction_type', '==', 'out'),
                ('created_at', '>=', prev_month_start),
                ('created_at', '<=', prev_month_end)
            ]
            
            success_prev, prev_transactions, _ = await self.db.query_documents(COLLECTIONS['inventory_transactions'], prev_filters)
            prev_usage = sum(abs(t.get('quantity', 0)) for t in prev_transactions) if success_prev else 0
            
            # Determine trend
            if prev_usage == 0:
                if current_usage > 0:
                    icon = "trending_up"
                    color = "green"
                else:
                    icon = "trending_flat"
                    color = "grey"
            else:
                change_percent = ((current_usage - prev_usage) / prev_usage) * 100
                if change_percent > 10:
                    icon = "trending_up"
                    color = "green"
                elif change_percent < -10:
                    icon = "trending_down"
                    color = "red"
                else:
                    icon = "trending_flat"
                    color = "grey"
            
            return {'icon': icon, 'color': color}
            
        except Exception as e:
            logger.error(f"Error calculating trend for {item_id}: {str(e)}")
            return {'icon': Icons.trending_flat, 'color': Colors.grey}

    async def _calculate_days_to_minimum(self, item: Dict[str, Any], monthly_usage: float) -> str:
        """Calculate days until stock reaches reorder level"""
        try:
            current_stock = item.get('current_stock', 0)
            reorder_level = item.get('reorder_level', 0)
            
            if monthly_usage <= 0 or current_stock <= reorder_level:
                return "N/A"
            
            # Calculate daily usage
            daily_usage = monthly_usage / 30
            
            # Days to reach reorder level
            stock_above_reorder = current_stock - reorder_level
            days_to_min = stock_above_reorder / daily_usage
            
            if days_to_min < 0:
                return "0d"
            elif days_to_min < 30:
                return f"{int(days_to_min)}d"
            else:
                return f"{int(days_to_min)}d"
                
        except Exception as e:
            logger.error(f"Error calculating days to min for {item.get('id')}: {str(e)}")
            return "N/A"

    async def _calculate_reorder_date(self, item: Dict[str, Any], monthly_usage: float) -> str:
        """Calculate estimated reorder date"""
        try:
            current_stock = item.get('current_stock', 0)
            reorder_level = item.get('reorder_level', 0)
            
            if monthly_usage <= 0 or current_stock <= reorder_level:
                return "Immediate"
            
            # Calculate daily usage
            daily_usage = monthly_usage / 30
            
            # Days to reach reorder level
            stock_above_reorder = current_stock - reorder_level
            days_to_reorder = stock_above_reorder / daily_usage
            
            if days_to_reorder < 0:
                return "Immediate"
            
            reorder_date = datetime.now() + timedelta(days=days_to_reorder)
            return reorder_date.strftime("%b %d")
                
        except Exception as e:
            logger.error(f"Error calculating reorder date for {item.get('id')}: {str(e)}")
            return "Unknown"

# Create global service instance
inventory_service = InventoryService()
