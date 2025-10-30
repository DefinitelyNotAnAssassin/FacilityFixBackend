from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from ..database.database_service import database_service
from ..database.collections import COLLECTIONS
from ..models.database_models import (
    Inventory, InventoryTransaction, InventoryRequest, 
    LowStockAlert, InventoryUsageAnalytics
)
import logging

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
                [('id', '==', item_id)]
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

                return True, request_data, None
            else:
                return False, None, error

        except Exception as e:
            error_msg = f"Error getting inventory request {request_id}: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

    async def get_requests_by_maintenance_task(self, maintenance_task_id: str) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Get all inventory requests linked to a maintenance task"""
        try:
            # Try both maintenance_task_id and reference_id fields
            success1, requests1, _ = await self.db.query_documents(
                COLLECTIONS['inventory_requests'],
                [('maintenance_task_id', '==', maintenance_task_id)]
            )
            
            success2, requests2, _ = await self.db.query_documents(
                COLLECTIONS['inventory_requests'],
                [('reference_id', '==', maintenance_task_id)]
            )
            
            # Combine and deduplicate results
            all_requests = []
            seen_ids = set()
            
            if success1 and requests1:
                for req in requests1:
                    req_id = req.get('_doc_id') or req.get('id')
                    if req_id and req_id not in seen_ids:
                        seen_ids.add(req_id)
                        all_requests.append(req)
            
            if success2 and requests2:
                for req in requests2:
                    req_id = req.get('_doc_id') or req.get('id')
                    if req_id and req_id not in seen_ids:
                        seen_ids.add(req_id)
                        all_requests.append(req)
            
            return True, all_requests, None
            
        except Exception as e:
            error_msg = f"Error getting inventory requests for maintenance task {maintenance_task_id}: {str(e)}"
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

# Create global service instance
inventory_service = InventoryService()
