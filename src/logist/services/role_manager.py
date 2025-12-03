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
            if filename.endswith(".json"):
                filepath = os.path.join(roles_config_path, filename)
                try:
                    with open(filepath, 'r') as f:
                        role_config = json.load(f)
                    # Only count as role if it has a 'name' field (valid role configuration)
                    if 'name' in role_config:
                        role_name = role_config['name']
                        role_description = role_config.get('description', f"Role configuration for {role_name}")
                        roles_data.append({
                            "name": role_name,
                            "description": role_description
                        })
                except json.JSONDecodeError:
                    print(f"⚠️  Warning: Skipping malformed JSON role file '{filename}'.")
                except Exception as e:
                    print(f"⚠️  Warning: Could not read role file '{filename}': {e}")
            elif filename.endswith(".md"):
                filepath = os.path.join(roles_config_path, filename)
                try:
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

        # Search for the role by filename - try multiple case variations and extensions
        candidate_filenames = [
            f"{role_name.lower()}.json",
            f"{role_name.lower()}.md",
            f"{role_name.title()}.json",
            f"{role_name.title()}.md"
        ]

        for filename in candidate_filenames:
            role_file_path = os.path.join(roles_config_path, filename)
            if os.path.exists(role_file_path):
                try:
                    if filename.endswith('.json'):
                        # Return JSON data
                        with open(role_file_path, 'r') as f:
                            role_data = json.load(f)
                        return json.dumps(role_data, indent=2)
                    else:
                        # Return .md content as text
                        with open(role_file_path, 'r') as f:
                            return f.read()
                except json.JSONDecodeError as e:
                    raise Exception(f"Failed to parse JSON role file '{filename}': {e}")
                except OSError as e:
                    raise Exception(f"Failed to read role file '{filename}': {e}")

        raise Exception(f"Role '{role_name}' not found.")