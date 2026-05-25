"""
Trade Nothing v6.0 — Dung's Abstract Argumentation Graph Solver
Computes the Grounded Extension (least fixed point of Dung's characteristic function)
to determine logically undefeated arguments in the adversarial debate.
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

    def characteristic_function(self, S: Set[str]) -> Set[str]:
        """
        Dung's characteristic function F(S).
        Returns the set of arguments defended by S.
        An argument x is defended by S if for every attacker y of x, S contains an attacker z of y.
        """
        defended = set()
        for x in self.arguments:
            # Get all attackers of x
            x_attackers = self.attackers[x]
            
            # If x has no attackers, it is trivially defended by S
            if not x_attackers:
                defended.add(x)
                continue
                
            # Check if S defends x against all of its attackers
            all_defended = True
            for y in x_attackers:
                # Find if there is any z in S that attacks y
                is_y_attacked_by_S = False
                for z in S:
                    # Does z attack y?
                    if (z, y) in self.attacks:
                        is_y_attacked_by_S = True
                        break
                if not is_y_attacked_by_S:
                    all_defended = False
                    break
                    
            if all_defended:
                defended.add(x)
                
        return defended

    def compute_grounded_extension(self) -> Set[str]:
        """
        Computes the Grounded Extension by iterating Dung's characteristic function
        starting from the empty set.
        """
        S = set()
        while True:
            next_S = self.characteristic_function(S)
            if next_S == S:
                break
            S = next_S
        return S

    def get_grounded_friction(self) -> float:
        """
        Computes the Argumentation Friction Index (AFI):
        AFI = |A \\ GE| / |A|
        If the argument set is empty, returns 0.0.
        """
        if not self.arguments:
            return 0.0
        ge = self.compute_grounded_extension()
        undefeated_count = len(ge)
        total_count = len(self.arguments)
        
        # AFI represents the proportion of arguments that are defeated or unresolved
        return float(total_count - undefeated_count) / total_count

# Quick test execution
if __name__ == "__main__":
    # Test simple attack chain: A attacks B, B attacks C
    # Grounded extension should be {A, C} (since A has no attackers, A is accepted;
    # B is attacked by A, B is rejected; C is attacked by B, but A attacks B, so C is defended and accepted)
    args = ["A", "B", "C"]
    atts = [("A", "B"), ("B", "C")]
    solver = DungSolver(args, atts)
    ge = solver.compute_grounded_extension()
    print("Grounded Extension (A -> B -> C):", ge)
    print("AFI (expected 1/3 = 0.33):", solver.get_grounded_friction())
    
    # Test cycle: A attacks B, B attacks A
    # Grounded extension should be empty (no undefeated starting points)
    args_cycle = ["A", "B"]
    atts_cycle = [("A", "B"), ("B", "A")]
    solver_cycle = DungSolver(args_cycle, atts_cycle)
    print("Grounded Extension (A <-> B):", solver_cycle.compute_grounded_extension())
    print("AFI (expected 1.0):", solver_cycle.get_grounded_friction())
