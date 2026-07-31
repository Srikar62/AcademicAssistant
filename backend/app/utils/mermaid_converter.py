"""
Mermaid mind map converter — transforms structured JSON into valid
Mermaid mindmap syntax.

This is the fix for the client-side plan's approach of asking the LLM
to generate Mermaid directly (which produces syntax errors).  Instead,
the LLM outputs structured JSON and this module converts it
deterministically.
"""

import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


def _sanitize_label(label: str) -> str:
    """
    Sanitize a label for use in Mermaid syntax.
    Remove or escape characters that break Mermaid parsing.
    """
    # Remove characters that break mermaid: (), [], {}, <>, `
    label = re.sub(r'[(){}\[\]<>`]', '', label)
    # Collapse multiple spaces
    label = re.sub(r'\s+', ' ', label).strip()
    # Truncate very long labels
    if len(label) > 60:
        label = label[:57] + "..."
    return label or "Untitled"


def json_to_mermaid(root: Dict[str, Any]) -> str:
    """
    Convert a mind map JSON tree to Mermaid mindmap syntax.

    Args:
        root: Dict with 'label' and 'children' keys.
              Children is a list of dicts with the same structure.

    Returns:
        A string containing valid Mermaid mindmap syntax.

    Example output:
        mindmap
          root((Main Topic))
            Subtopic 1
              Detail 1a
              Detail 1b
            Subtopic 2
              Detail 2a
    """
    lines = ["mindmap"]
    _build_tree(root, lines, depth=1, is_root=True)
    return "\n".join(lines)


def _build_tree(
    node: Dict[str, Any],
    lines: List[str],
    depth: int,
    is_root: bool = False,
) -> None:
    """
    Recursively build Mermaid mindmap lines from a tree node.

    Args:
        node: Current node with 'label' and optional 'children'.
        lines: Accumulator list of output lines.
        depth: Current indentation depth.
        is_root: Whether this is the root node (uses special syntax).
    """
    indent = "  " * depth
    label = _sanitize_label(node.get("label", "Untitled"))

    if is_root:
        # Root uses double-parentheses syntax for rounded shape
        lines.append(f"{indent}root(({label}))")
    else:
        lines.append(f"{indent}{label}")

    children = node.get("children", [])
    for child in children:
        if isinstance(child, dict) and child.get("label"):
            _build_tree(child, lines, depth + 1, is_root=False)


def validate_mermaid_mindmap(mermaid_text: str) -> bool:
    """
    Basic validation of Mermaid mindmap syntax.

    Checks:
      - Starts with 'mindmap'
      - Has a root node
      - Has at least one child node
      - No obviously broken lines

    Returns:
        True if the syntax looks valid, False otherwise.
    """
    lines = [l.strip() for l in mermaid_text.strip().split("\n") if l.strip()]

    if not lines:
        return False

    if lines[0] != "mindmap":
        return False

    if len(lines) < 3:
        return False

    # Check for root node
    has_root = any("root(" in line for line in lines)
    if not has_root:
        return False

    return True


def parse_mindmap_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse and normalize the LLM's mind map JSON response.

    Handles common LLM quirks:
      - Root at top level vs nested under 'root' key
      - Missing 'children' key (default to empty list)
      - String children (convert to node dicts)

    Args:
        data: The raw JSON dict from the LLM.

    Returns:
        Normalized root node dict with 'label' and 'children'.

    Raises:
        ValueError: If the structure is fundamentally invalid.
    """
    # Handle case where root is nested under a 'root' key
    if "root" in data and isinstance(data["root"], dict):
        root = data["root"]
    elif "label" in data:
        root = data
    else:
        raise ValueError(
            "Mind map JSON must have either a 'root' key with a node dict, "
            "or a top-level 'label' key."
        )

    if not root.get("label"):
        raise ValueError("Root node must have a non-empty 'label'.")

    # Normalize children recursively
    _normalize_children(root)
    return root


def _normalize_children(node: Dict[str, Any]) -> None:
    """Recursively ensure all children are proper node dicts."""
    children = node.get("children", [])
    if not isinstance(children, list):
        node["children"] = []
        return

    normalized = []
    for child in children:
        if isinstance(child, str):
            normalized.append({"label": child, "children": []})
        elif isinstance(child, dict):
            if not child.get("label"):
                continue
            _normalize_children(child)
            normalized.append(child)

    node["children"] = normalized
