#!/usr/bin/env python3
import re

# Read the file
with open(r"app/main.py", 'r') as f:
    content = f.read()

# Pattern to find the chat router line
pattern = r'(\s+)\("app\.routers\.chat", "Chat"\),'

# Replacement with chat + staff_scheduling
replacement = r'\1("app.routers.chat", "Chat"),\n\1("app.routers.staff_scheduling", "Staff Scheduling"),'

# Replace
new_content = re.sub(pattern, replacement, content)

# Write back
with open(r"app/main.py", 'w') as f:
    f.write(new_content)

print("Staff scheduling router added successfully!")

# Verify
with open(r"app/main.py", 'r') as f:
    if "staff_scheduling" in f.read():
        print("✓ Verified: staff_scheduling is now in the file")
    else:
        print("✗ Error: staff_scheduling not found")
