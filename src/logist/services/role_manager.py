"""
Role Manager Service

Handles agent role management and loading from configuration files.
"""

import json
import os
from typing import List


class RoleManagerService:
    """Manages agent roles, loading them from configuration."""

    def list_roles(self, jobs_dir: str) -> list:
        """List all available agent roles by reading configuration files."""
        roles_data = []
        roles_config_path = jobs_dir

        if not os.path.exists(roles_config_path):
            print(f"⚠️  Warning: Role configuration directory '{roles_config_path}' not found.")
            return []

        for filename in os.listdir(roles_config_path):
            if filename.endswith(".md"):
                filepath = os.path.join(roles_config_path, filename)
                try:
                    with open(filepath, 'r') as f:
                        role_content = f.read()
                    # Extract role name from filename (worker.md -> Worker)
                    role_name = filename.replace('.md', '').title()
                    roles_data.append({
                        "name": role_name,
                        "description": f"Role configuration for {role_name}"
                    })
                except Exception as e:
                    print(f"⚠️  Warning: Could not read role file '{filename}': {e}")
        return roles_data

    def inspect_role(self, role_name: str, jobs_dir: str) -> str:
        """Display the detailed configuration for a specific role."""
        roles_config_path = jobs_dir

        # Search for the role by filename (worker.md, supervisor.md, system.md)
        expected_filename = f"{role_name.lower()}.md"
        role_file_path = os.path.join(roles_config_path, expected_filename)

        if os.path.exists(role_file_path):
            try:
                with open(role_file_path, 'r') as f:
                    return f.read()
            except OSError as e:
                raise Exception(f"Failed to read role file '{expected_filename}': {e}")

        raise Exception(f"Role '{role_name}' not found (expected file: {expected_filename}).")