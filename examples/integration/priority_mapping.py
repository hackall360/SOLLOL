"""
Example: Priority mapping and configuration.

This example demonstrates SOLLOL's priority system and how to configure
custom priority mappings for different use cases.

Demonstrates:
- Using semantic priority levels
- Role-based priority mapping
- Task-based priority mapping
- Custom priority schemes
- Priority mapper for complex systems
"""

from sollol.sync_wrapper import OllamaPool
from sollol.priority_helpers import (
    Priority,
    PriorityMapper,
    get_priority_for_role,
    get_priority_for_task,
    register_role_priority,
    register_task_priority,
    explain_priority_system,
    list_available_roles,
    list_available_tasks,
)


def semantic_priorities_example():
    """Example using semantic priority constants."""
    print("=== Semantic Priority Levels ===\n")

    pool = OllamaPool.auto_configure()

    # Use semantic priority levels for clarity
    tasks = [
        ("Critical user-facing request", Priority.CRITICAL),
        ("Important analysis task", Priority.HIGH),
        ("Normal processing", Priority.NORMAL),
        ("Background indexing", Priority.LOW),
        ("Batch job", Priority.BATCH),
    ]

    for task_name, priority in tasks:
        print(f"{task_name} (priority={priority})")
        try:
            response = pool.chat(
                model="llama3.2",
                messages=[{"role": "user", "content": task_name}],
                priority=priority,
                timeout=30,
            )
            print(f"  ✓ Completed\n")
        except Exception as e:
            print(f"  ✗ Failed: {e}\n")


def role_based_priorities_example():
    """Example using role-based priority mapping."""
    print("\n=== Role-Based Priority Mapping ===\n")

    pool = OllamaPool.auto_configure()

    # Show available predefined roles
    print("Available predefined roles:")
    for role in list_available_roles():
        priority = get_priority_for_role(role)
        print(f"  {role}: {priority}")

    print("\nUsing role-based priorities:\n")

    # Define agents with roles
    agents = [
        {"name": "User Assistant", "role": "assistant"},
        {"name": "Content Reviewer", "role": "reviewer"},
        {"name": "Background Indexer", "role": "indexer"},
    ]

    for agent in agents:
        priority = get_priority_for_role(agent["role"])
        print(f"{agent['name']} ({agent['role']}) - priority={priority}")

        try:
            response = pool.chat(
                model="llama3.2",
                messages=[{"role": "user", "content": f"Task for {agent['name']}"}],
                priority=priority,
                timeout=30,
            )
            print(f"  ✓ Completed\n")
        except Exception as e:
            print(f"  ✗ Failed: {e}\n")


def task_based_priorities_example():
    """Example using task-based priority mapping."""
    print("\n=== Task-Based Priority Mapping ===\n")

    pool = OllamaPool.auto_configure()

    # Show available predefined task types
    print("Available predefined task types:")
    for task_type in list_available_tasks():
        priority = get_priority_for_task(task_type)
        print(f"  {task_type}: {priority}")

    print("\nUsing task-based priorities:\n")

    # Define tasks with types
    tasks = [
        {"description": "Real-time chat", "type": "interactive"},
        {"description": "Document analysis", "type": "analysis"},
        {"description": "Text summarization", "type": "summarization"},
        {"description": "Batch indexing", "type": "indexing"},
    ]

    for task in tasks:
        priority = get_priority_for_task(task["type"])
        print(f"{task['description']} ({task['type']}) - priority={priority}")

        try:
            response = pool.chat(
                model="llama3.2",
                messages=[{"role": "user", "content": task["description"]}],
                priority=priority,
                timeout=30,
            )
            print(f"  ✓ Completed\n")
        except Exception as e:
            print(f"  ✗ Failed: {e}\n")


def custom_priority_registration():
    """Example registering custom priorities."""
    print("\n=== Custom Priority Registration ===\n")

    # Register custom role priorities
    register_role_priority("custom_agent", 9)
    register_role_priority("low_priority_agent", 2)

    # Register custom task priorities
    register_task_priority("custom_task", 8)
    register_task_priority("monitoring", 3)

    print("Registered custom priorities:")
    print(f"  custom_agent: {get_priority_for_role('custom_agent')}")
    print(f"  low_priority_agent: {get_priority_for_role('low_priority_agent')}")
    print(f"  custom_task: {get_priority_for_task('custom_task')}")
    print(f"  monitoring: {get_priority_for_task('monitoring')}")


def priority_mapper_example():
    """Example using PriorityMapper for complex systems."""
    print("\n=== PriorityMapper for Complex Systems ===\n")

    # Create custom priority mapper
    mapper = PriorityMapper()

    # Add custom mappings
    mapper.add_role("frontend_agent", Priority.URGENT)
    mapper.add_role("backend_worker", Priority.NORMAL)
    mapper.add_role("maintenance_job", Priority.LOW)

    mapper.add_task("user_query", Priority.HIGH)
    mapper.add_task("analytics", Priority.BELOW_NORMAL)
    mapper.add_task("cleanup", Priority.BATCH)

    # List all mappings
    print("Custom role mappings:")
    for role, priority in sorted(mapper.list_roles().items()):
        print(f"  {role}: {priority}")

    print("\nCustom task mappings:")
    for task, priority in sorted(mapper.list_tasks().items()):
        print(f"  {task}: {priority}")

    # Use mapper
    pool = OllamaPool.auto_configure()

    agents = ["frontend_agent", "backend_worker", "maintenance_job"]

    print("\nExecuting agents with custom priorities:\n")
    for agent in agents:
        priority = mapper.get_role_priority(agent)
        print(f"{agent} (priority={priority})")

        try:
            response = pool.chat(
                model="llama3.2",
                messages=[{"role": "user", "content": f"Task for {agent}"}],
                priority=priority,
                timeout=30,
            )
            print(f"  ✓ Completed\n")
        except Exception as e:
            print(f"  ✗ Failed: {e}\n")


def dynamic_priority_adjustment():
    """Example with dynamic priority adjustment based on conditions."""
    print("\n=== Dynamic Priority Adjustment ===\n")

    pool = OllamaPool.auto_configure()

    def get_dynamic_priority(user_tier: str, task_complexity: str) -> int:
        """Calculate priority based on user tier and task complexity."""
        base_priority = {
            "free": 3,
            "basic": 5,
            "premium": 8,
            "enterprise": 10,
        }.get(user_tier, 5)

        complexity_boost = {"simple": 0, "medium": 1, "complex": 2}.get(
            task_complexity, 0
        )

        return min(base_priority + complexity_boost, 10)

    # Simulate different user scenarios
    scenarios = [
        {"user": "free_user", "tier": "free", "complexity": "simple"},
        {"user": "premium_user", "tier": "premium", "complexity": "medium"},
        {"user": "enterprise_user", "tier": "enterprise", "complexity": "complex"},
    ]

    for scenario in scenarios:
        priority = get_dynamic_priority(scenario["tier"], scenario["complexity"])
        print(
            f"{scenario['user']} ({scenario['tier']}, {scenario['complexity']}) - priority={priority}"
        )

        try:
            response = pool.chat(
                model="llama3.2",
                messages=[
                    {"role": "user", "content": f"Task for {scenario['user']}"}
                ],
                priority=priority,
                timeout=30,
            )
            print(f"  ✓ Completed\n")
        except Exception as e:
            print(f"  ✗ Failed: {e}\n")


def print_priority_system_info():
    """Print information about SOLLOL's priority system."""
    print(explain_priority_system())


if __name__ == "__main__":
    # Show priority system explanation
    print_priority_system_info()

    # Run examples
    try:
        semantic_priorities_example()
    except Exception as e:
        print(f"Semantic priorities example failed: {e}")

    try:
        role_based_priorities_example()
    except Exception as e:
        print(f"Role-based priorities example failed: {e}")

    try:
        task_based_priorities_example()
    except Exception as e:
        print(f"Task-based priorities example failed: {e}")

    try:
        custom_priority_registration()
    except Exception as e:
        print(f"Custom registration example failed: {e}")

    try:
        priority_mapper_example()
    except Exception as e:
        print(f"Priority mapper example failed: {e}")

    try:
        dynamic_priority_adjustment()
    except Exception as e:
        print(f"Dynamic priority example failed: {e}")
