import networkx as nx


class FibreDigitalTwin:
    """
    Digital twin of a linear fibre-optic network topology.

    Represents the physical layer as a graph of spans (nodes) connected by
    fibre segments (edges). Supports fault injection and healing simulation.
    """

    # OSNR values assigned during healing (dB)
    _OSNR_AFTER_REROUTE = 20.5
    _OSNR_AMPLIFIER_BOOST = 3.0
    _OSNR_HEALTHY = 22.0

    def __init__(self, num_spans: int = 15):
        self.graph = nx.Graph()
        self.num_spans = num_spans
        self._build_topology()

    # ── Topology ────────────────────────────────────────────────────────────────

    def _build_topology(self):
        """Build a linear chain topology with nominal healthy parameters."""
        for i in range(self.num_spans):
            self.graph.add_node(i, status="healthy", osnr=self._OSNR_HEALTHY, power=0.0)

        # Linear primary path + implicit protection via alternate routing
        for i in range(self.num_spans - 1):
            self.graph.add_edge(i, i + 1, loss=0.01, latency=5.0, status="active")

    # ── Fault Injection ─────────────────────────────────────────────────────────

    def inject_fault(self, span_id: int, fault_type: str = "cut"):
        """
        Simulate a fault on a given span.

        Args:
            span_id:    Node index to affect.
            fault_type: "cut" for a full fibre cut, anything else for a
                        partial degradation event.
        """
        if not self.graph.has_node(span_id):
            return
        self.graph.nodes[span_id]["status"] = "faulty"
        self.graph.nodes[span_id]["osnr"] = 7.0 if fault_type == "cut" else 14.0

    # ── Healing ─────────────────────────────────────────────────────────────────

    def apply_healing(self, action: str, span_id: int):
        """
        Apply a healing action to a span in the digital twin.

        Supported action keywords (case-insensitive):
          - "reroute" / "protection" → full restoration (healed)
          - "amplifier" / "adjust"   → partial recovery (recovering)

        Args:
            action:  The recommended_action string from the decision engine.
            span_id: Target span node index.
        """
        if not self.graph.has_node(span_id):
            print(f"Warning: span {span_id} does not exist in the digital twin.")
            return

        node = self.graph.nodes[span_id]
        action_lower = action.lower()

        if "reroute" in action_lower or "protection" in action_lower:
            # Full failover to protection path — span restored to near-nominal
            node["status"] = "healed"
            node["osnr"] = self._OSNR_AFTER_REROUTE

        elif "amplifier" in action_lower or "adjust" in action_lower:
            # Amplifier gain adjustment — partial OSNR recovery
            node["status"] = "recovering"
            node["osnr"] = min(node["osnr"] + self._OSNR_AMPLIFIER_BOOST, self._OSNR_HEALTHY)

        else:
            print(f"Warning: unrecognised healing action '{action}' — no twin update applied.")
            return

        print(f"Healing applied: [{action}] on span {span_id} -> status={node['status']}, osnr={node['osnr']:.1f} dB")

    # ── State Inspection ────────────────────────────────────────────────────────

    def get_state(self) -> dict:
        """Return current state of all nodes and edges."""
        return {
            "nodes": dict(self.graph.nodes(data=True)),
            "edges": {str(e): d for e, d in self.graph.edges(data=True)},
        }

    def get_span_status(self, span_id: int) -> dict | None:
        """Return the current attributes of a single span node."""
        if self.graph.has_node(span_id):
            return dict(self.graph.nodes[span_id])
        return None