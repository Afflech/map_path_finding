class MultiCriteriaCostCalculator:
    def __init__(self, w_time=1.0, w_traffic=1.0, w_flood=1.0, w_turn=1.0):
        self.w_time = w_time
        self.w_traffic = w_traffic
        self.w_flood = w_flood
        self.w_turn = w_turn

    def evaluate_edge(self, length_m, speed_ms, traffic_length_m, is_flooded, is_jammed, is_blocked):
        """
        Tính toán chi phí dựa trên nhiều tiêu chí.
        Trả về (total_cost, breakdown_dict)
        """
        if is_blocked:
            return float('inf'), {}

        base_time = length_m / speed_ms
        
        # Traffic penalty
        traffic_time = traffic_length_m / speed_ms
        traffic_penalty = traffic_time - base_time
        
        if is_jammed:
            # Fallback jammed node
            traffic_penalty += traffic_time * 7.0 # JAMMED_PENALTY_FACTOR = 8.0
            
        # Flood penalty
        flood_risk = 0.0
        if is_flooded:
            # FLOODED_BIKE_PENALTY_FACTOR = 20.0
            total_before_flood = base_time + traffic_penalty
            flood_risk = total_before_flood * 19.0

        total_cost = (self.w_time * base_time) + \
                     (self.w_traffic * traffic_penalty) + \
                     (self.w_flood * flood_risk)

        breakdown = {
            "travel_time_s": base_time,
            "traffic_penalty_s": traffic_penalty,
            "flood_risk_s": flood_risk
        }
        return total_cost, breakdown

    def evaluate_turn(self, turn_penalty_s):
        total_cost = self.w_turn * turn_penalty_s
        breakdown = {
            "turn_penalty_s": turn_penalty_s
        }
        return total_cost, breakdown
