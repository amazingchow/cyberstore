"""Tree widget for displaying R2 buckets."""

from __future__ import annotations

from textual.message import Message
from textual.widgets import Tree


class BucketTree(Tree):
    """A tree widget showing available R2 buckets."""

    class BucketSelected(Message):
        """Fired when a bucket is selected."""

        def __init__(self, bucket_name: str) -> None:
            self.bucket_name = bucket_name
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__("BUCKETS", **kwargs)
        self.show_root = True
        self.guide_depth = 3

    def set_buckets(self, bucket_names: list[str]) -> None:
        """Populate the tree with bucket names."""
        self.clear()
        for name in sorted(bucket_names):
            self.root.add_leaf(f"🪣 {name}", data=name)
        self.root.expand()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle bucket node selection."""
        if event.node.data is not None:
            self.post_message(self.BucketSelected(event.node.data))
