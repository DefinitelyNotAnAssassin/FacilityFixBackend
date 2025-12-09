#!/usr/bin/env python3
"""
Sample script to test maintenance recurrence flow using the example task payload provided.

1. Create a maintenance task with recurrence "quarterly" and parts/checklist
2. Mark the task as completed -> should trigger recursion
3. Verify that a new recurring task was created with:
   - preserved assigned_to
   - inventory reservation(s) created
   - checklist copied and reset to uncompleted
4. Verify notifications created for staff and admin

Run with:
    py scripts/sample_maintenance_recurrence_test.py

This script uses the backend services directly; run this from the repo root with
Python environment configured for this project (firebase, etc.).
"""

import asyncio
import sys
from datetime import datetime, timedelta

sys.path.insert(0, '.')

from app.services.maintenance_task_service import maintenance_task_service
from app.routers.maintenance import submit_assessment, SubmitAssessmentRequest
from app.services.notification_manager import notification_manager
from app.services.inventory_service import inventory_service
from app.services.user_id_service import user_id_service
from app.database.database_service import database_service
from app.database.collections import COLLECTIONS


def format_ts(ts):
    return ts.isoformat() if hasattr(ts, 'isoformat') else str(ts)


async def main():
    print('\n=== Sample Maintenance Recurrence Test ===')

    # Find an admin user id - fallback to first admin in notifications manager helper
    admin_ids = await notification_manager._get_admin_user_ids()
    if not admin_ids:
        print('No admin users available - cannot create task')
        return
    admin_uid = admin_ids[0]
    print(f'Using admin UID: {admin_uid}')

    # Example staff mapping as provided (S-0007)
    staff_identifier = 'S-0007'

    # Attempt to convert to Firebase UID via user_id_service; fallback to staff_identifier
    staff_profile = await user_id_service.get_staff_profile_from_staff_id(staff_identifier)
    staff_uid = staff_profile.id if staff_profile else staff_identifier
    print(f'Staff UID to use: {staff_uid} (profile found: {bool(staff_profile)})')

    # Build payload with the fields provided in the example
    scheduled_date = datetime.utcnow() + timedelta(seconds=5)

    payload = {
        'building_id': 'default_building',
        'task_title': 'Light Replacement',
        'task_description': 'Replace fluorescent tubes with LED equivalents in Lobby',
        'location': 'Lobby',
        'scheduled_date': scheduled_date,
        'recurrence_type': 'quarterly',
        'assigned_to': staff_identifier,  # use staff id (S-0007) - backend will map or accept as UID
        'priority': 'Medium',
        'category': 'preventive',
        'status': 'scheduled',
        'parts_used': [
            {
                'inventory_id': 'CON-ELC-1593',
                'quantity': 6
            },
            {
                'inventory_id': 'CON-ELC-3094',
                'quantity': 2
            }
        ],
        'checklist_completed': [
            {'id': '1765217251515', 'task': 'Remove the old fluorescent tubes and dispose of it in the hazardous waste bin.', 'completed': True},
            {'id': '1765217260550', 'task': 'Install the new LED T8 tube (18W Cool White).', 'completed': True}
        ],
        'task_type_id': 'TT-2025-00016',
        'task_type': 'internal',
        'maintenance_type': 'corrective',
    }

    # Create the task
    print('\n-> Creating maintenance task...')
    task = await maintenance_task_service.create_task(admin_uid, payload)
    print(f'Created task: {task.id} ({task.task_title})')

    # Wait a moment for any async creation hooks (like reservations)
    await asyncio.sleep(1)

    # Print inventory reservation ids, if any
    inv_res_ids = getattr(task, 'inventory_reservation_ids', []) or []
    print(f'Inventory reservations created: {len(inv_res_ids)} -> {inv_res_ids}')

    # Now mark the task as completed (this should trigger recurrence)
    print('\n-> Marking task as completed to trigger recurrence...')
    updated = await maintenance_task_service.update_task(task.id, {'status': 'completed', 'completed_at': datetime.utcnow()})
    if not updated:
        print('Failed to mark task as completed')
        return
    print(f'Task {task.id} marked as completed')

    # Allow some seconds for the recurrence job and notifications
    await asyncio.sleep(3)

    # ------------------
    # STAFF SUBMITS ASSESSMENT (simulate router call) -> notify admins
    # ------------------
    print('\n-> Simulating staff submitting assessment (submit_assessment endpoint)...')
    from app.routers.maintenance import SubmitAssessmentRequest, submit_assessment
    # Build current_user context for staff
    staff_current_user = {
        'uid': staff_uid,
        'role': 'staff',
        'name': getattr(staff_profile, 'first_name', '') + ' ' + getattr(staff_profile, 'last_name', '') if staff_profile else staff_uid
    }

    req = SubmitAssessmentRequest(assessment='tapos napo', assessment_notes=None)
    # Call submit_assessment endpoint function directly with the current_user context
    await submit_assessment(task.id, req, current_user=staff_current_user)
    print('Staff assessment submitted via router function')

    # Allow time for notifications and status updates to persist
    await asyncio.sleep(2)

    # Fetch updated task and verify status changed to 'ready_for_next_cycle'
    updated_task = await maintenance_task_service.get_task(task.id)
    new_status = getattr(updated_task, 'status', None)
    print(f"Updated task status after assessment: {new_status}")
    if new_status == 'ready_for_next_cycle':
        print('✓ Task status successfully set to ready_for_next_cycle')
    else:
        print('✗ Task status did not change to ready_for_next_cycle')

    # Find the newly created recurring task - check for tasks with same title and scheduled_date > original
    print('\n-> Finding the newly created recurring task...')
    success, tasks, err = await database_service.query_documents(COLLECTIONS['maintenance_tasks'], filters=[('task_title', '==', payload['task_title'])])
    if not success:
        print('Failed to query tasks:', err)
        return

    # Filter tasks that aren't the original and scheduled_date > original scheduled
    recurring_tasks = []
    for t in tasks:
        if (t.get('id') != task.id) and ('scheduled_date' in t):
            # parse scheduled_date if string
            sched = t['scheduled_date']
            if isinstance(sched, str):
                try:
                    sched_dt = datetime.fromisoformat(sched.replace('Z', '+00:00'))
                except Exception:
                    continue
            else:
                sched_dt = sched
            if sched_dt > scheduled_date:
                recurring_tasks.append(t)

    if not recurring_tasks:
        print('No recurring task found')
        return

    recurring_task = sorted(recurring_tasks, key=lambda x: x.get('scheduled_date'))[0]
    print(f'Found recurring task: {recurring_task.get("id")} scheduled at {recurring_task.get("scheduled_date")}')

    # Check assigned_to preserved
    print('Assigned to (orig):', payload['assigned_to'], ' => recurring assigned_to:', recurring_task.get('assigned_to'))

    # Check checklist: should be present and reset to completed == False
    print('\nChecklist on recurring task:')
    for item in recurring_task.get('checklist_completed', []):
        print(' -', item.get('id'), item.get('task'), 'completed:', item.get('completed'))

    # Check parts_used/inventory reservations exist
    print('\nParts on recurring task:')
    parts = recurring_task.get('parts_used') or []
    if parts:
        print('Recurring parts:', parts)
    else:
        print('No parts used in recurring task')

    # Query notifications for staff and admins (search by related entity id)
    print('\n-> Verifying notifications...')
    notif_filters = [('related_entity_id', '==', recurring_task.get('id'))]
    success, notifications, err = await database_service.query_documents(COLLECTIONS['notifications'], filters=notif_filters)
    if not success:
        print('Failed to query notifications:', err)
        return

    print(f'Notifications for recurring task {recurring_task.get("id")}: {len(notifications)}')
    for n in notifications:
        print(' -', n.get('recipient_id'), n.get('notification_type'), n.get('title'))

    # Cleanup: delete tasks and notifications created for this test
    print('\n-> Cleaning up created test data...')
    try:
        # Delete recurring task
        succ, err = await database_service.delete_document(COLLECTIONS['maintenance_tasks'], recurring_task.get('id'))
        print('Deleted recurring task:', recurring_task.get('id'), 'success=', succ)
        # Delete original task
        succ, err = await database_service.delete_document(COLLECTIONS['maintenance_tasks'], task.id)
        print('Deleted original task:', task.id, 'success=', succ)
        # Delete notifications related to this recurring task
        for n in notifications:
            nid = n.get('id') or n.get('_doc_id')
            if nid:
                s, e = await database_service.delete_document(COLLECTIONS['notifications'], nid)
                print('Deleted notification', nid, 'success=', s)
    except Exception as e:
        print('Cleanup failed:', e)

    print('\n=== Sample test finished ===')

    # Additional check: admin notifications for assessment on original task
    print('\n-> Verifying admin notifications for assessment (original task)...')
    notif_filters = [('related_entity_id', '==', task.id)]
    success, notifications_for_task, err = await database_service.query_documents(COLLECTIONS['notifications'], filters=notif_filters)
    if not success:
        print('Failed to query notifications for original task:', err)
    else:
        print(f'Notifications for original task {task.id}: {len(notifications_for_task)}')
        for n in notifications_for_task:
            print(' -', n.get('recipient_id'), n.get('notification_type'), n.get('title'))
        # Check admin notifications exist titled 'Maintenance Task Completed'
        admin_notifs = [n for n in notifications_for_task if n.get('title') == 'Maintenance Task Completed']
        if admin_notifs:
            print(f'Found {len(admin_notifs)} admin notification(s) for Maintenance Task Completed')
        else:
            print('No admin notification found for Maintenance Task Completed on original task')


if __name__ == '__main__':
    asyncio.run(main())
