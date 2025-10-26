import sqlite3
import spacy
import re
from datetime import datetime, timedelta
import random

class Chatbot:
    def __init__(self):
        # Load spaCy model
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except:
            # If model not found, download it
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
            self.nlp = spacy.load("en_core_web_sm")
        
        # Define intents and their keywords
        self.intents = {
            "greeting": ["hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening"],
            "order_placement": ["order", "buy", "purchase", "add to cart", "checkout", "want to buy", "want to order"],
            "order_tracking": ["track", "status", "where is", "delivery status", "shipping status", "order status", "my order"],
            "order_cancellation": ["cancel", "stop", "return", "refund", "don't want"],
            "product_recommendation": ["recommend", "suggestion", "similar", "like", "suggest", "what else", "more products"],
            "help": ["help", "support", "assistance", "guide", "how to", "how do I"],
            "goodbye": ["bye", "goodbye", "see you", "talk to you later", "thanks", "thank you"]
        }
        
        # Product name patterns for extraction
        self.product_pattern = re.compile(r'(idli|dosa|upma|poha|pancake|cake|vanilla|strawberry|thandai|badam|chutney|sambar|rasam)\s*(mix)?', re.IGNORECASE)
        
        # Order ID pattern
        self.order_id_pattern = re.compile(r'order\s*(?:id|number)?\s*[#]?\s*(\d+)', re.IGNORECASE)
        
        # Simple number pattern for order ID
        self.number_pattern = re.compile(r'#?(\d+)')
    
    def detect_intent(self, message):
        """Detect the user's intent from their message"""
        doc = self.nlp(message.lower())
        
        # Check for each intent
        max_score = 0
        detected_intent = "unknown"
        
        for intent, keywords in self.intents.items():
            score = 0
            for keyword in keywords:
                if keyword in message.lower():
                    score += 1
            
            if score > max_score:
                max_score = score
                detected_intent = intent
        
        # If no intent was detected with keywords, use spaCy similarity
        if detected_intent == "unknown":
            for intent, keywords in self.intents.items():
                for keyword in keywords:
                    keyword_doc = self.nlp(keyword)
                    try:
                        similarity = doc.similarity(keyword_doc)
                        if similarity > 0.7 and similarity > max_score:  # Threshold for similarity
                            max_score = similarity
                            detected_intent = intent
                    except:
                        # Handle case where similarity can't be computed
                        pass
        
        # Special case for single word "track" or "cancel"
        if message.lower().strip() == "track":
            return "order_tracking"
        if message.lower().strip() == "cancel":
            return "order_cancellation"
        
        # Handle "cancel #order" cases
        if "cancel" in message.lower() and any(word.isdigit() for word in message.split()):
            return "order_cancellation"
        
        return detected_intent
    
    def extract_product_name(self, message):
        """Extract product name from user message"""
        match = self.product_pattern.search(message)
        if match:
            product_name = match.group(0).strip()
            # Ensure "Mix" is capitalized for database matching
            if "mix" in product_name.lower() and not product_name.endswith("Mix"):
                product_name = product_name.replace("mix", "Mix")
            return product_name
        return None
    
    def extract_order_id(self, message):
        """Extract order ID from user message"""
        # First try the standard order ID pattern
        match = self.order_id_pattern.search(message)
        if match:
            return match.group(1)
        
        # Then try to find any number in the message as a fallback
        match = self.number_pattern.search(message)
        if match:
            return match.group(1)
        
        # If no number found, return None
        return None
    
    def get_product_by_name(self, product_name):
        """Get product details from database by name"""
        conn = sqlite3.connect('ecommerce.db')
        c = conn.cursor()
        
        # Use LIKE for partial matching
        c.execute('SELECT * FROM products WHERE name LIKE ?', (f'%{product_name}%',))
        product = c.fetchone()
        conn.close()
        
        return product
    
    def get_order_status(self, order_id, user_id):
        """Get order status from database"""
        conn = sqlite3.connect('ecommerce.db')
        c = conn.cursor()
        
        c.execute('''
            SELECT o.id, o.status, o.created_at, o.total_amount,
                   GROUP_CONCAT(p.name || ' (x' || oi.quantity || ')') as items
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            JOIN products p ON oi.product_id = p.id
            WHERE o.id = ? AND o.user_id = ?
            GROUP BY o.id
        ''', (order_id, user_id))
        
        order = c.fetchone()
        conn.close()
        
        return order
    
    def get_user_orders(self, user_id, limit=3):
        """Get recent orders for a user"""
        conn = sqlite3.connect('ecommerce.db')
        c = conn.cursor()
        
        c.execute('''
            SELECT o.id, o.status, o.created_at, o.total_amount
            FROM orders o
            WHERE o.user_id = ?
            ORDER BY o.created_at DESC
            LIMIT ?
        ''', (user_id, limit))
        
        orders = c.fetchall()
        conn.close()
        
        return orders
    
    def can_cancel_order(self, order_id, user_id):
        """Check if an order can be cancelled (within 24 hours)"""
        conn = sqlite3.connect('ecommerce.db')
        c = conn.cursor()
        
        c.execute('''
            SELECT created_at, status
            FROM orders
            WHERE id = ? AND user_id = ?
        ''', (order_id, user_id))
        
        order = c.fetchone()
        conn.close()
        
        if not order:
            return False, "Order not found"
        
        if order[1] == 'cancelled':
            return False, "Order is already cancelled"
        
        order_date = datetime.strptime(order[0], '%Y-%m-%d %H:%M:%S')
        if datetime.now() - order_date > timedelta(hours=24):
            return False, "Order cannot be cancelled as it's been more than 24 hours"
        
        return True, "Order can be cancelled"
    
    def get_product_recommendations(self, user_id):
        """Get product recommendations based on user's order history"""
        conn = sqlite3.connect('ecommerce.db')
        c = conn.cursor()
        
        # Get products the user has ordered before
        c.execute('''
            SELECT DISTINCT p.id, p.name
            FROM products p
            JOIN order_items oi ON p.id = oi.product_id
            JOIN orders o ON oi.order_id = o.id
            WHERE o.user_id = ?
            LIMIT 3
        ''', (user_id,))
        
        user_products = c.fetchall()
        
        # If user has no order history, recommend popular products
        if not user_products:
            c.execute('SELECT id, name FROM products ORDER BY RANDOM() LIMIT 3')
            recommendations = c.fetchall()
        else:
            # Get similar products (simple implementation - in real world, use ML)
            product_ids = [p[0] for p in user_products]
            placeholders = ','.join(['?'] * len(product_ids))
            
            c.execute(f'''
                SELECT id, name FROM products 
                WHERE id NOT IN ({placeholders})
                ORDER BY RANDOM() LIMIT 3
            ''', product_ids)
            
            recommendations = c.fetchall()
        
        conn.close()
        return recommendations
    
    def process_message(self, message, user_id=None, session=None):
        """Process user message and return appropriate response"""
        intent = self.detect_intent(message)
        
        if intent == "greeting":
            return "Hello! How can I help you today? You can ask me about products, track your orders, or get recommendations."
        
        elif intent == "goodbye":
            return "Thank you for chatting! If you need anything else, I'm here to help."
        
        elif intent == "help":
            return "I can help you with: placing orders, tracking your orders, cancelling orders, and recommending products. What would you like to do?"
        
        elif intent == "order_placement":
            product_name = self.extract_product_name(message)
            
            if not product_name:
                return "What product would you like to order? We have Idli Mix, Dosa Mix, Upma Mix, and many more!"
            
            product = self.get_product_by_name(product_name)
            
            if not product:
                return f"I couldn't find {product_name} in our inventory. Would you like to see our available products?"
            
            # Add product to cart in session
            if session is not None:
                if 'cart' not in session:
                    session['cart'] = {}
                
                cart = session['cart']
                product_id = str(product[0])
                if product_id in cart:
                    cart[product_id] += 1
                else:
                    cart[product_id] = 1
                
                session['cart'] = cart
                return f"{product[1]} has been added to your cart. Would you like to proceed to checkout or continue shopping?"
            else:
                return "Please log in to add products to your cart."
        
        elif intent == "order_tracking":
            order_id = self.extract_order_id(message)
            
            if not order_id:
                if user_id:
                    orders = self.get_user_orders(user_id)
                    if orders:
                        orders_text = "\n".join([f"Order #{o[0]}: {o[1]}, Total: ₹{o[3]}" for o in orders])
                        return f"Here are your recent orders:\n{orders_text}\n\nWhich order would you like to track?"
                
                return "Please provide your order ID so I can track it for you."
            
            if not user_id:
                return "Please log in to track your order."
            
            order = self.get_order_status(order_id, user_id)
            
            if not order:
                return f"I couldn't find order #{order_id}. Please check the order number and try again."
            
            status = order[1]
            items = order[4] if len(order) > 4 else "your items"
            return f"Your order #{order_id} is currently {status}. The total amount is ₹{order[3]}. Items: {items}"
        
        elif intent == "order_cancellation":
            order_id = self.extract_order_id(message)
            
            if not order_id:
                if user_id:
                    orders = self.get_user_orders(user_id)
                    if orders:
                        orders_text = "\n".join([f"Order #{o[0]}: {o[1]}, Total: ₹{o[3]}" for o in orders])
                        return f"Here are your recent orders:\n{orders_text}\n\nWhich order would you like to cancel?"
                
                return "Please provide your order ID so I can cancel it for you."
            
            if not user_id:
                return "Please log in to cancel your order."
            
            can_cancel, reason = self.can_cancel_order(order_id, user_id)
            
            if can_cancel:
                # Call the cancel_order route to update the database
                return f"I've initiated the cancellation for order #{order_id}. You'll receive a refund soon."
            else:
                return reason
        
        elif intent == "product_recommendation":
            if not user_id:
                return "Please log in to get personalized recommendations."
            
            recommendations = self.get_product_recommendations(user_id)
            
            if not recommendations:
                return "I don't have enough information to make recommendations yet. Try exploring our product catalog!"
            
            rec_text = "Based on your preferences, you might like: " + ", ".join([r[1] for r in recommendations])
            return rec_text
        
        else:
            # Handle cases where the intent is unclear
            product_name = self.extract_product_name(message)
            if product_name:
                product = self.get_product_by_name(product_name)
                if product:
                    return f"Are you looking to add {product[1]} to your cart? Please say 'add {product[1]} to cart' to proceed."
            
            return "I'm not sure I understand. Would you like to place an order, track an order, or get product recommendations?"