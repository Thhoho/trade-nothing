"""
Trade Nothing v10.0 — Continuous Fuzzy Dung's Argumentation Graph Solver
Computes continuous belief valuations for arguments in the adversarial debate,
solving the binary degradation issue using iterative numeric fixed-points.
"""

from typing import Set, Tuple, List, Dict

class DungSolver:
    def __init__(self, arguments: List[str], attacks: List[Tuple[str, str]]):
        """
        :param arguments: List of argument identifiers, e.g., ["Claim_1", "Claim_2"]
        :param attacks: List of attack tuples, where ("Claim_A", "Claim_B") means A attacks B
        """
        self.arguments = set(arguments)
        self.attacks = set(attacks)
        
        # Build map: argument -> set of its attackers
        self.attackers: Dict[str, Set[str]] = {arg: set() for arg in self.arguments}
        for attacker, target in self.attacks:
            if target in self.attackers and attacker in self.arguments:
                self.attackers[target].add(attacker)

    def get_node_confidence(self, arg: str) -> float:
        """Calculate continuous confidence score for an argument node based on its semantic class."""
        if "[Proxy Data Anchor" in arg or "[Audit Node" in arg:
            return 1.0
        elif "[Vision Node" in arg:
            return 0.8
        elif "[Narrative Node" in arg:
            return 0.6
        else:
            # System penalty nodes or legacy/simulated text
            if arg.startswith("System:"):
                return 1.0
            return 0.9  # Default confidence

    def get_attack_strength(self, attacker: str, target: str) -> float:
        """Calculate continuous attack strength of an edge based on attacker class."""
        if attacker.startswith("System:"):
            return 1.0
        if "[Audit Attack]" in attacker:
            return 0.95
        if "[Vision Audit]" in attacker:
            return 0.8
        return 0.85  # Default attack strength

    def compute_fuzzy_valuations(self, max_iter: int = 50, dampening: float = 0.5) -> Dict[str, float]:
        """
        Computes fuzzy continuous belief valuations for all arguments.
        Uses iteration with dampening to guarantee convergence under odd-loop cycles.
        If the solver does not converge within max_iter, returns the mathematical average
        of the last 5 iteration states to eliminate limit cycle oscillations.
        """
        # Initialize belief valuation to node confidence scores
        V = {arg: self.get_node_confidence(arg) for arg in self.arguments}
        
        # Keep track of the last 5 iteration states for limit cycle smoothing
        history: List[Dict[str, float]] = []
        converged = False
        
        for k in range(max_iter):
            next_V = {}
            max_delta = 0.0
            
            for x in self.arguments:
                confidence = self.get_node_confidence(x)
                attackers = self.attackers[x]
                
                if not attackers:
                    # No attackers -> belief matches its own confidence
                    product = 1.0
                else:
                    product = 1.0
                    for y in attackers:
                        weight = self.get_attack_strength(y, x)
                        product *= (1.0 - weight * V[y])
                        
                # Next belief value calculation
                val = confidence * product
                
                # Apply dampening relaxation to guarantee convergence
                next_val = dampening * val + (1.0 - dampening) * V[x]
                next_V[x] = next_val
                
                delta = abs(next_val - V[x])
                if delta > max_delta:
                    max_delta = delta
            
            V = next_V
            
            # Store in history, keeping at most the last 5 states
            history.append(V.copy())
            if len(history) > 5:
                history.pop(0)
                
            # If converged, stop early
            if max_delta < 1e-5:
                converged = True
                break
                
        if not converged and len(history) >= 5:
            # Not converged: average the last 5 states to eliminate periodic limit cycles
            smoothed_V = {}
            for x in self.arguments:
                smoothed_V[x] = sum(state[x] for state in history) / len(history)
            return smoothed_V
            
        return V

    def compute_grounded_extension(self) -> Set[str]:
        """
        Computes the Grounded Extension by binarizing the fuzzy continuous belief valuations.
        An argument is accepted if its fuzzy belief valuation >= 0.5.
        """
        V = self.compute_fuzzy_valuations()
        return {arg for arg, val in V.items() if val >= 0.5}

    def get_grounded_friction(self) -> float:
        """
        Computes the Continuous Argumentation Friction Index (AFI):
        AFI = (1/|A|) * sum_{x in A} (1 - V(x))
        AFI represents the average belief loss across the entire debate graph.
        """
        if not self.arguments:
            return 0.0
        V = self.compute_fuzzy_valuations()
        total_loss = sum(1.0 - val for val in V.values())
        return total_loss / len(self.arguments)

# Quick test execution
if __name__ == "__main__":
    # Test simple attack chain: A attacks B, B attacks C
    args = ["A", "B", "C"]
    atts = [("A", "B"), ("B", "C")]
    solver = DungSolver(args, atts)
    ge = solver.compute_grounded_extension()
    print("Fuzzy Grounded Extension (A -> B -> C):", ge)
    print("Continuous AFI (expected continuous friction):", solver.get_grounded_friction())
    
    # Test cycle: A attacks B, B attacks A (Fuzzy solver should converge under dampening)
    args_cycle = ["A", "B"]
    atts_cycle = [("A", "B"), ("B", "A")]
    solver_cycle = DungSolver(args_cycle, atts_cycle)
    print("Fuzzy Grounded Extension (A <-> B):", solver_cycle.compute_grounded_extension())
    print("Continuous AFI for Cycle:", solver_cycle.get_grounded_friction())
