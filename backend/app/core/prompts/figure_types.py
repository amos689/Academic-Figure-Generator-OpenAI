"""
Figure type definitions for the academic-figure-generator service.

Each figure type corresponds to a category of visual used in top-tier academic
papers (CVPR, NeurIPS, Nature, IEEE, etc.). The type determines:

  - Default aspect ratio fed to the OpenAI Image API
  - Prompt structuring guidance (referenced by the system prompt)
  - Which sections of a paper typically produce this figure type
  - Typical content and visual vocabulary

Usage:
    from app.core.prompts.figure_types import FIGURE_TYPES, DEFAULT_ASPECT_RATIOS

    ft = FIGURE_TYPES["overall_framework"]
    print(ft["default_aspect_ratio"])   # "16:9"
    print(ft["description"])
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Figure type registry
# ---------------------------------------------------------------------------

FIGURE_TYPES: dict[str, dict] = {

    # ── 1. OVERALL FRAMEWORK ────────────────────────────────────────────────
    "overall_framework": {
        "slug":                "overall_framework",
        "display_name":        "Overall Framework (总体框架图)",
        "default_aspect_ratio": "16:9",
        "typical_paper_sections": [
            "Introduction",
            "Method",
            "Proposed Approach",
            "System Overview",
        ],
        "description": (
            "An end-to-end pipeline figure showing the complete flow from raw input "
            "through all processing stages to the final output. Uses a horizontal "
            "left-to-right layout with labeled stage blocks connected by annotated "
            "arrows indicating data types (e.g., tensor dimensions). Stage groups are "
            "enclosed in dashed bounding boxes labeled with their role (Encoder, "
            "Decoder, Loss). Suitable as Figure 1 of the paper."
        ),
        "typical_content": [
            "Input modality block (image, text, video, point cloud)",
            "Feature extraction / backbone block",
            "Core processing / novel module blocks",
            "Prediction head block",
            "Output visualization",
            "Inter-stage data-flow arrows with tensor shape annotations",
            "Optional: supervision / loss branches",
            "Optional: skip connections or multi-scale paths",
        ],
        "layout_hint": "horizontal-pipeline",
        "min_panels": 4,
        "max_panels": 8,
        "recommended_color_usage": {
            "primary":    "Main novel module borders and fills",
            "secondary":  "Standard/baseline module borders",
            "tertiary":   "Grouping bounding box borders",
            "arrow":      "All inter-stage arrows",
            "section_bg": "Stage block fill tints",
        },
    },

    # ── 2. NETWORK ARCHITECTURE ─────────────────────────────────────────────
    "network_architecture": {
        "slug":                "network_architecture",
        "display_name":        "Network Architecture (网络架构图)",
        "default_aspect_ratio": "16:9",
        "typical_paper_sections": [
            "Method",
            "Architecture",
            "Model Design",
            "Proposed Method",
            "Approach",
        ],
        "description": (
            "A detailed layer-by-layer diagram of the neural network or computational "
            "graph at the core of the paper. Shows individual layer types (Conv, BN, "
            "Attention, MLP, Pool) as distinct geometric shapes with parameter counts "
            "and tensor dimension labels on connecting arrows. Residual/skip connections "
            "are shown as curved arcs over the main path. Repeating blocks may use a "
            "macro-view on the left and a zoomed detail panel on the right, linked by "
            "a dashed callout."
        ),
        "typical_content": [
            "Individual layer blocks (Conv, BN, Activation, Attention, MLP, Pool)",
            "Tensor shape annotations on connecting arrows (B×C×H×W format)",
            "Residual/skip connections as curved arcs",
            "Repeating block notation (×N label)",
            "Parameter count per module",
            "Macro overview + micro zoomed detail (dual-panel optional)",
            "Stage/phase grouping with dashed enclosures",
        ],
        "layout_hint": "horizontal-layers",
        "min_panels": 1,
        "max_panels": 3,
        "recommended_color_usage": {
            "primary":    "Novel/proposed layer types",
            "secondary":  "Standard layer types (Conv, BN, Act)",
            "tertiary":   "Skip/residual connection arrows",
            "arrow":      "Main forward-pass arrows",
            "section_bg": "Layer block fill tints",
        },
    },

    # ── 3. MODULE DETAIL ────────────────────────────────────────────────────
    "module_detail": {
        "slug":                "module_detail",
        "display_name":        "Module Detail (模块细节图)",
        "default_aspect_ratio": "4:3",
        "typical_paper_sections": [
            "Key Component",
            "Novel Module",
            "Attention Mechanism",
            "Loss Function",
            "Fusion Strategy",
            "Core Contribution",
        ],
        "description": (
            "A close-up figure zooming into one specific novel contribution of the paper "
            "and revealing its internal data-flow mechanics. Occupies 60–70% of the canvas "
            "with the central mechanism, showing operation nodes (⊗ matmul, ⊕ add, [;] concat, "
            "σ softmax), color-coded data streams (queries, keys, values), and formula overlays. "
            "A small thumbnail in the corner situates the module within the broader system. "
            "Time and space complexity annotations appear at the bottom."
        ),
        "typical_content": [
            "Central mechanism with internal operation graph",
            "Operation nodes: ⊗ (matmul), ⊕ (add), [;] (concat), σ (softmax/sigmoid)",
            "Color-coded data streams by semantic role",
            "Key formula embedded as inline math",
            "Context thumbnail showing module position in full architecture",
            "Time complexity annotation: O(n²d) style",
            "Space complexity annotation",
            "Input/output tensor shape labels",
        ],
        "layout_hint": "central-detail-with-context",
        "min_panels": 1,
        "max_panels": 2,
        "recommended_color_usage": {
            "primary":    "Query/main input stream",
            "secondary":  "Key stream",
            "tertiary":   "Value stream",
            "arrow":      "All data-flow arrows",
            "section_bg": "Operation node fills",
        },
    },

    # ── 4. COMPARISON / ABLATION ────────────────────────────────────────────
    "comparison_ablation": {
        "slug":                "comparison_ablation",
        "display_name":        "Comparison / Ablation (对比消融图)",
        "default_aspect_ratio": "16:9",
        "typical_paper_sections": [
            "Experiments",
            "Results",
            "Ablation Study",
            "Comparison with State-of-the-Art",
            "Qualitative Results",
            "Quantitative Evaluation",
        ],
        "description": (
            "A grid figure comparing the proposed method against baselines (or comparing "
            "ablation variants), with rows representing input samples or ablation configurations "
            "and columns representing different methods. Column headers are method names; the "
            "proposed method column is visually highlighted with a primary-color background tint "
            "and a dashed highlight box. Key metric values appear below each column header. "
            "Zoom insets (×4) highlight regions of interest in select cells."
        ),
        "typical_content": [
            "Grid of N×M panels (N methods × M input samples or ablation variants)",
            "Column headers: method names (bolded for proposed method)",
            "Row labels: input type, scene category, or ablation config",
            "Metric values below each column header (best value highlighted)",
            "Proposed method column highlighted with dashed primary-color border",
            "Optional: horizontal bar chart row summarizing all metrics",
            "Zoom insets with magnifying-glass icon on key regions",
            "Difference maps or error heatmaps for image-level comparisons",
        ],
        "layout_hint": "comparison-grid",
        "min_panels": 4,
        "max_panels": 20,
        "recommended_color_usage": {
            "primary":    "Proposed method column header and highlight box",
            "secondary":  "Best metric value highlights",
            "tertiary":   "Zoom inset borders",
            "arrow":      "Callout arrows to zoom insets",
            "section_bg": "Cell backgrounds and header fills",
        },
    },

    # ── 5. DATA BEHAVIOR ────────────────────────────────────────────────────
    "data_behavior": {
        "slug":                "data_behavior",
        "display_name":        "Data Behavior (数据行为图)",
        "default_aspect_ratio": "4:3",
        "typical_paper_sections": [
            "Analysis",
            "Visualization",
            "Feature Analysis",
            "Attention Visualization",
            "Representation Quality",
            "Training Dynamics",
            "Dataset Statistics",
        ],
        "description": (
            "A visualization figure showing how data or learned representations behave "
            "during processing or across training. Can be a multi-panel layout combining "
            "attention heatmaps, t-SNE/UMAP scatter plots, training curves, or feature map "
            "grids. Each panel type follows strict conventions: heatmaps use white→primary "
            "sequential scale with colorbar; scatter plots use one palette color per class; "
            "training curves use solid line for proposed method and dashed for baselines "
            "with shaded ±1σ confidence intervals."
        ),
        "typical_content": [
            "Attention heatmaps overlaid on reference images (sequential color scale)",
            "t-SNE or UMAP scatter plots with class cluster labels",
            "Training/validation loss and metric curves over epochs",
            "Feature map grids (4×4 or 8×8 thumbnail arrays)",
            "Histogram or KDE plots of feature distributions",
            "Confusion matrices with normalized cell values",
            "PR curves or ROC curves for detection/classification tasks",
            "Correlation heatmaps between learned features",
        ],
        "layout_hint": "visualization-panels",
        "min_panels": 1,
        "max_panels": 6,
        "recommended_color_usage": {
            "primary":    "Proposed method curve / dominant heatmap color",
            "secondary":  "Baseline curves / secondary class cluster",
            "tertiary":   "Third-class cluster / tertiary data series",
            "arrow":      "Annotation arrows pointing to notable data regions",
            "section_bg": "Plot background fill (very light, inside axes area)",
        },
    },
}

# ---------------------------------------------------------------------------
# Convenience lookups
# ---------------------------------------------------------------------------

FIGURE_TYPE_SLUGS: list[str] = list(FIGURE_TYPES.keys())

DEFAULT_ASPECT_RATIOS: dict[str, str] = {
    slug: info["default_aspect_ratio"]
    for slug, info in FIGURE_TYPES.items()
}

FIGURE_TYPE_DISPLAY_NAMES: dict[str, str] = {
    slug: info["display_name"]
    for slug, info in FIGURE_TYPES.items()
}


def get_figure_type(slug: str) -> dict:
    """
    Return figure type metadata by slug.

    Raises:
        KeyError: If slug is not a known figure type.
    """
    if slug not in FIGURE_TYPES:
        raise KeyError(
            f"Unknown figure type '{slug}'. "
            f"Valid types: {FIGURE_TYPE_SLUGS}"
        )
    return FIGURE_TYPES[slug]


def get_default_aspect_ratio(slug: str) -> str:
    """Return the default aspect ratio string for a given figure type slug."""
    return FIGURE_TYPES.get(slug, FIGURE_TYPES["overall_framework"])["default_aspect_ratio"]


__all__ = [
    "FIGURE_TYPES",
    "FIGURE_TYPE_SLUGS",
    "DEFAULT_ASPECT_RATIOS",
    "FIGURE_TYPE_DISPLAY_NAMES",
    "get_figure_type",
    "get_default_aspect_ratio",
]
