import random
import networkx as nx

class ACOZoneSolver:
    def __init__(self, zone_manager, start_zone, end_zone, num_ants=10, iterations=5, alpha=1.0, beta=2.0, evaporation_rate=0.5):
        self.zone_manager = zone_manager
        self.start_zone = start_zone
        self.end_zone = end_zone
        self.num_ants = num_ants
        self.iterations = iterations
        self.alpha = alpha
        self.beta = beta
        self.evaporation_rate = evaporation_rate
        self.pheromones = {}

    def run(self, top_k=3):
        best_paths = []
        path_costs = []
        
        for u, v in self.zone_manager.zone_graph.edges():
            self.pheromones[(u, v)] = 1.0
            
        for it in range(self.iterations):
            paths = []
            for _ in range(self.num_ants):
                path = self._construct_path()
                if path:
                    cost = self._calculate_cost(path)
                    paths.append((path, cost))
                    
            if not paths:
                continue
                
            self._update_pheromones(paths)
            
            for p, c in paths:
                # Lưu dưới dạng tuple để check trùng
                p_tuple = tuple(p)
                if p_tuple not in best_paths:
                    best_paths.append(p_tuple)
                    path_costs.append(c)

        sorted_pairs = sorted(zip(best_paths, path_costs), key=lambda x: x[1])
        unique_paths = []
        for p, c in sorted_pairs:
            p_list = list(p)
            if p_list not in unique_paths:
                unique_paths.append(p_list)
            if len(unique_paths) >= top_k:
                break
                
        return unique_paths

    def _construct_path(self):
        path = [self.start_zone]
        current = self.start_zone
        visited = {current}
        
        while current != self.end_zone:
            neighbors = list(self.zone_manager.zone_graph.successors(current))
            unvisited = [n for n in neighbors if n not in visited]
            
            if not unvisited:
                return None
                
            probs = []
            for n in unvisited:
                tau = self.pheromones.get((current, n), 1.0)
                dist_to_end = self._distance(n, self.end_zone)
                eta = 1.0 / (dist_to_end + 1e-6)
                p = (tau ** self.alpha) * (eta ** self.beta)
                probs.append(p)
                
            sum_probs = sum(probs)
            if sum_probs == 0:
                probs = [1.0/len(probs)] * len(probs)
            else:
                probs = [p/sum_probs for p in probs]
                
            next_node = random.choices(unvisited, weights=probs, k=1)[0]
            path.append(next_node)
            visited.add(next_node)
            current = next_node
            
        return path

    def _calculate_cost(self, path):
        cost = 0
        for i in range(len(path)-1):
            u, v = path[i], path[i+1]
            data = self.zone_manager.zone_graph.get_edge_data(u, v)
            cost += data['weight']
        return cost

    def _update_pheromones(self, paths):
        for k in self.pheromones:
            self.pheromones[k] *= (1.0 - self.evaporation_rate)
            
        for path, cost in paths:
            deposit = 1000.0 / (cost + 1e-6)
            for i in range(len(path)-1):
                u, v = path[i], path[i+1]
                self.pheromones[(u, v)] = self.pheromones.get((u, v), 1.0) + deposit

    def _distance(self, z1, z2):
        lat1, lon1 = self.zone_manager.zone_centers[z1]
        lat2, lon2 = self.zone_manager.zone_centers[z2]
        return self.zone_manager._haversine(lat1, lon1, lat2, lon2)
