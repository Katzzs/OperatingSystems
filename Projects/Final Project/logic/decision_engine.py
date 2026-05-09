"""
Decision Engine - Warehouse stock intelligence
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
import config
from services.data_service import DataService


class DecisionEngine:
    """The brain of the warehouse - evaluates stock situations and provides recommendations"""
    
    def __init__(self, data_service: DataService):
        self.data_service = data_service
        self.weights = {
            'urgency': config.URGENCY_WEIGHT,
            'frequency': config.FREQUENCY_WEIGHT,
            'impact': config.IMPACT_WEIGHT,
            'recency': config.RECENCY_WEIGHT
        }
    
    def _get_product_stock(self, product_id: int) -> int:
        """Get total stock for a product across all locations"""
        return self.data_service.get_total_stock_for_product(product_id)
    
    def _get_stock_coverage_days(self, product_id: int) -> int:
        """Estimate how many days of stock remain based on recent OUT rate"""
        stats = self.data_service.get_movement_stats(product_id, days=30)
        total_stock = self._get_product_stock(product_id)
        
        if stats['out_qty'] <= 0:
            return 999  # No recent sales = effectively infinite
        
        daily_rate = stats['out_qty'] / 30.0
        return int(total_stock / daily_rate)
    
    def calculate_restock_score(self, product: Dict) -> tuple:
        """
        Calculate restock priority score for a product.
        Returns: (score, priority_level, reason)
        """
        total_stock = self._get_product_stock(product['id'])
        reorder_point = product.get('reorder_point', 20)
        reorder_qty = product.get('reorder_qty', 50)
        max_stock = product.get('max_stock', 200)
        unit_cost = product.get('unit_cost', 0.0)
        
        # Urgency: How close to stockout?
        if total_stock <= 0:
            urgency = 1.0
        elif total_stock <= reorder_point * 0.5:
            urgency = 0.9
        elif total_stock <= reorder_point:
            urgency = 0.7
        elif total_stock <= reorder_point * 1.5:
            urgency = 0.5
        else:
            urgency = 0.1
        
        # Impact: Financial value at risk
        stock_value = total_stock * unit_cost
        reorder_value = reorder_qty * unit_cost
        impact = min(reorder_value / 1000.0, 1.0)  # Normalize: $1000 = max impact
        
        # Frequency: How fast does it sell?
        stats = self.data_service.get_movement_stats(product['id'], days=30)
        if stats['out_qty'] > 0:
            daily_rate = stats['out_qty'] / 30.0
            days_until_stockout = total_stock / daily_rate if daily_rate > 0 else 999
            
            if days_until_stockout <= 3:
                frequency_score = 1.0
            elif days_until_stockout <= 7:
                frequency_score = 0.8
            elif days_until_stockout <= 14:
                frequency_score = 0.5
            else:
                frequency_score = 0.2
        else:
            frequency_score = 0.0  # Dead stock - low restock priority
        
        # Recency: When was it last received?
        movements = self.data_service.get_movements(product['id'], limit=1)
        if movements and movements[0]['movement_type'] == 'IN':
            last_in = self._parse_timestamp(movements[0].get('timestamp'))
            days_since = (datetime.now() - last_in).days
            if days_since > 30:
                recency = 0.6
            else:
                recency = 0.2
        else:
            recency = 0.3
        
        score = (
            urgency * self.weights['urgency'] +
            impact * self.weights['impact'] +
            frequency_score * self.weights['frequency'] +
            recency * self.weights['recency']
        ) * 100
        
        score = round(score, 2)
        
        if score >= config.HIGH_PRIORITY_THRESHOLD:
            priority = "HIGH"
        elif score >= config.MEDIUM_PRIORITY_THRESHOLD:
            priority = "MEDIUM"
        else:
            priority = "LOW"
        
        # Build reason
        reasons = []
        if total_stock <= 0:
            reasons.append(f"STOCKOUT: {product['name']} has zero stock")
        elif total_stock <= reorder_point:
            reasons.append(f"Below reorder point ({total_stock}/{reorder_point} {product['unit']})")
        
        if stats['out_qty'] > 0:
            daily_rate = stats['out_qty'] / 30.0
            days_left = int(total_stock / daily_rate) if daily_rate > 0 else 999
            if days_left <= 7:
                reasons.append(f"Only ~{days_left} days of stock remaining at current pace")
        
        if not reasons:
            reasons.append("Routine replenishment")
        
        reason = ". ".join(reasons) + "."
        return score, priority, reason

    def _parse_timestamp(self, ts: Optional[str]) -> datetime:
        """
        Robust timestamp parsing for SQLite CURRENT_TIMESTAMP and ISO strings.
        Falls back to 'now' if parsing fails.
        """
        if not ts:
            return datetime.now()
        try:
            # Handles both 'YYYY-MM-DD HH:MM:SS' and ISO-8601 variants
            return datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
        except Exception:
            try:
                return datetime.strptime(str(ts), "%Y-%m-%d %H:%M:%S")
            except Exception:
                return datetime.now()
    
    def generate_restock_recommendation(self, product: Dict) -> Optional[Dict]:
        """Generate a restock recommendation for a product"""
        score, priority, reason = self.calculate_restock_score(product)
        
        if priority == "LOW":
            return None
        
        total_stock = self._get_product_stock(product['id'])
        reorder_qty = product.get('reorder_qty', 50)
        unit_cost = product.get('unit_cost', 0.0)
        supplier = self.data_service.get_supplier(product.get('supplier_id')) if product.get('supplier_id') else None
        
        # Estimate lead time coverage
        stats = self.data_service.get_movement_stats(product['id'], days=30)
        if stats['out_qty'] > 0:
            daily_rate = stats['out_qty'] / 30.0
            lead_time = supplier['lead_time_days'] if supplier else 7
            demand_during_lead = daily_rate * lead_time
            safety_gap = total_stock - demand_during_lead
            
            if safety_gap < 0:
                reason += f" Insufficient safety stock for {lead_time}d lead time."
        
        return {
            'action_type': 'restock',
            'target_id': product['id'],
            'target_type': 'product',
            'target_name': product['name'],
            'sku': product['sku'],
            'score': score,
            'priority_level': priority,
            'reason': reason,
            'suggested_qty': reorder_qty,
            'est_cost': round(reorder_qty * unit_cost, 2),
            'confidence': self._calculate_confidence('restock', product['id'])
        }
    
    def generate_expiry_recommendation(self, product: Dict) -> Optional[Dict]:
        """Generate recommendation for products nearing expiry"""
        if not product.get('expiry_date'):
            return None
        
        expiry = datetime.strptime(product['expiry_date'], '%Y-%m-%d')
        days_until = (expiry - datetime.now()).days
        total_stock = self._get_product_stock(product['id'])
        
        if days_until > 30 or total_stock <= 0:
            return None
        
        if days_until <= 0:
            score = 95.0
            priority = "HIGH"
            reason = f"{product['name']} has EXPIRED with {total_stock} {product['unit']} in stock. Mark for disposal immediately."
        elif days_until <= 7:
            score = 80.0
            priority = "HIGH"
            reason = f"{product['name']} expires in {days_until} days with {total_stock} {product['unit']} remaining. Consider discount or disposal."
        elif days_until <= 14:
            score = 60.0
            priority = "MEDIUM"
            reason = f"{product['name']} expires in {days_until} days with {total_stock} {product['unit']} remaining. Monitor closely."
        else:
            score = 45.0
            priority = "MEDIUM"
            reason = f"{product['name']} expires in {days_until} days with {total_stock} {product['unit']} remaining. Plan clearance."
        
        return {
            'action_type': 'clear_expiring',
            'target_id': product['id'],
            'target_type': 'product',
            'target_name': product['name'],
            'sku': product['sku'],
            'score': score,
            'priority_level': priority,
            'reason': reason,
            'suggested_qty': total_stock,
            'est_cost': 0,
            'confidence': 0.85
        }
    
    def generate_dead_stock_recommendation(self, product: Dict) -> Optional[Dict]:
        """Recommend action for dead stock (no movement in 90 days)"""
        stats = self.data_service.get_movement_stats(product['id'], days=90)
        total_stock = self._get_product_stock(product['id'])
        
        if stats['out_qty'] > 0 or total_stock <= 0:
            return None
        
        stock_value = total_stock * product.get('unit_cost', 0.0)
        
        score = min(50 + stock_value / 50, 75)
        priority = "MEDIUM"
        reason = f"{product['name']} has had ZERO sales in 90 days with {total_stock} {product['unit']} ({stock_value} value) tied up in stock. Consider clearance or return."
        
        return {
            'action_type': 'clear_dead_stock',
            'target_id': product['id'],
            'target_type': 'product',
            'target_name': product['name'],
            'sku': product['sku'],
            'score': round(score, 2),
            'priority_level': priority,
            'reason': reason,
            'suggested_qty': total_stock,
            'est_cost': round(stock_value, 2),
            'confidence': 0.7
        }
    
    def _calculate_confidence(self, action_type: str, target_id: int) -> float:
        base_confidence = 0.5
        # For now, return base; behavior tracker will adjust
        return round(base_confidence, 2)
    
    def get_all_recommendations(self, limit: int = 15) -> List[Dict]:
        """Get all current warehouse recommendations, sorted by score"""
        recommendations = []
        
        products = self.data_service.get_all_products()
        
        for product in products:
            # Restock recommendations
            rec = self.generate_restock_recommendation(product)
            if rec:
                recommendations.append(rec)
            
            # Expiry recommendations
            rec = self.generate_expiry_recommendation(product)
            if rec:
                recommendations.append(rec)
            
            # Dead stock recommendations
            rec = self.generate_dead_stock_recommendation(product)
            if rec:
                recommendations.append(rec)
        
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        return recommendations[:limit]
    
    def get_top_recommendation(self) -> Optional[Dict]:
        recommendations = self.get_all_recommendations(limit=1)
        return recommendations[0] if recommendations else None
    
    def generate_insights(self) -> List[Dict]:
        """Generate warehouse insights"""
        insights = []
        
        # Low stock / reorder alerts
        below_reorder = self.data_service.get_below_reorder_products()
        if below_reorder:
            critical = [p for p in below_reorder if self._get_product_stock(p['id']) <= 0]
            if critical:
                insights.append({
                    'type': 'risk',
                    'title': f'{len(critical)} products at ZERO stock',
                    'description': 'Immediate stockout risk affecting fulfillment',
                    'severity': 'critical' if len(critical) > 3 else 'high'
                })
            else:
                insights.append({
                    'type': 'risk',
                    'title': f'{len(below_reorder)} products below reorder point',
                    'description': 'Reorder needed to maintain service levels',
                    'severity': 'high' if len(below_reorder) > 5 else 'medium'
                })
        
        # Expiry insights
        expiring = self.data_service.get_expiring_products(days=14)
        if expiring:
            insights.append({
                'type': 'risk',
                'title': f'{len(expiring)} products expiring within 14 days',
                'description': 'Potential write-off risk if not cleared',
                'severity': 'high' if len(expiring) > 5 else 'medium'
            })
        
        # Dead stock
        dead = self.data_service.get_dead_stock(days=90)
        if dead:
            dead_value = sum(p['total_stock'] * p.get('unit_cost', 0) for p in dead)
            insights.append({
                'type': 'trend',
                'title': f'{len(dead)} dead stock items ({dead_value:.0f} tied up)',
                'description': 'No sales in 90 days - capital is frozen',
                'severity': 'medium'
            })
        
        # Overall inventory health
        total_value = self.data_service.get_inventory_value()
        products = self.data_service.get_all_products()
        locations = self.data_service.get_all_locations()
        
        health_score = 100
        if below_reorder:
            health_score -= len(below_reorder) * 5
        if expiring:
            health_score -= len(expiring) * 3
        if dead:
            health_score -= len(dead) * 2
        health_score = max(0, min(100, health_score))
        
        insights.append({
            'type': 'summary',
            'title': f'Warehouse Health: {health_score}%',
            'description': f'Tracking {len(products)} SKUs across {len(locations)} locations. Inventory value: {total_value:.2f}',
            'severity': 'low' if health_score > 80 else ('medium' if health_score > 50 else 'high')
        })
        
        return insights
    
    def generate_purchase_plan(self) -> List[Dict]:
        """Generate suggested purchase order lines based on current stock levels"""
        plan = []
        below_reorder = self.data_service.get_below_reorder_products()
        
        for product in below_reorder:
            total_stock = self._get_product_stock(product['id'])
            reorder_qty = product.get('reorder_qty', 50)
            unit_cost = product.get('unit_cost', 0.0)
            supplier = self.data_service.get_supplier(product.get('supplier_id')) if product.get('supplier_id') else None
            
            plan.append({
                'product_id': product['id'],
                'sku': product['sku'],
                'name': product['name'],
                'current_stock': total_stock,
                'reorder_point': product.get('reorder_point', 20),
                'suggested_qty': reorder_qty,
                'unit_cost': unit_cost,
                'line_total': round(reorder_qty * unit_cost, 2),
                'supplier_id': product.get('supplier_id'),
                'supplier_name': supplier['name'] if supplier else 'No supplier',
                'lead_time': supplier['lead_time_days'] if supplier else 7,
                'reason': f"Stock ({total_stock}) below reorder point ({product.get('reorder_point', 20)})"
            })
        
        return sorted(plan, key=lambda x: x['line_total'], reverse=True)
    
    def analyze_abc(self) -> Dict[str, List[Dict]]:
        """ABC analysis based on inventory value movement"""
        products = self.data_service.get_all_products()
        
        product_values = []
        for product in products:
            stock = self._get_product_stock(product['id'])
            value = stock * product.get('unit_cost', 0.0)
            product_values.append({
                'product': product,
                'stock_value': value,
                'stock': stock
            })
        
        product_values.sort(key=lambda x: x['stock_value'], reverse=True)
        total_value = sum(p['stock_value'] for p in product_values)
        
        if total_value == 0:
            return {'A': [], 'B': [], 'C': []}
        
        cumulative = 0
        result = {'A': [], 'B': [], 'C': []}
        
        for pv in product_values:
            cumulative += pv['stock_value']
            pct = cumulative / total_value
            
            entry = {
                'sku': pv['product']['sku'],
                'name': pv['product']['name'],
                'stock_value': round(pv['stock_value'], 2),
                'stock': pv['stock'],
                'cumulative_pct': round(pct * 100, 1)
            }
            
            if pct <= 0.80:
                result['A'].append(entry)
            elif pct <= 0.95:
                result['B'].append(entry)
            else:
                result['C'].append(entry)
        
        return result
