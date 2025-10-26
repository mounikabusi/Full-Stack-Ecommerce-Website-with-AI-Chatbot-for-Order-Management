const axios = require('axios');

// Place an order
async function placeOrder(event, product, quantity, userId) {
    try {
        const response = await axios.post('http://127.0.0.1:5000/api/place_order', {
            user_id: userId,
            product: product,
            quantity: quantity,
        });
        return response.data;
    } catch (error) {
        return { error: error.response?.data?.error || 'An error occurred while placing the order.' };
    }
}

// Cancel an order
async function cancelOrder(event, orderId, userId) {
    try {
        const response = await axios.post('http://127.0.0.1:5000/api/cancel_order', {
            user_id: userId,
            order_id: orderId,
        });
        return response.data;
    } catch (error) {
        return { error: error.response?.data?.error || 'An error occurred while canceling the order.' };
    }
}

// View orders
async function viewOrders(event, userId) {
    try {
        const response = await axios.get(`http://127.0.0.1:5000/api/view_orders`, {
            params: { user_id: userId },
        });
        return response.data;
    } catch (error) {
        return { error: error.response?.data?.error || 'An error occurred while retrieving orders.' };
    }
}

module.exports = async (event, { args }) => {
    const userId = event.target; // Assuming userId is the event target
    const { action, product, quantity, orderId } = args;

    let result;
    if (action === 'place_order') {
        result = await placeOrder(event, product, quantity, userId);
    } else if (action === 'cancel_order') {
        result = await cancelOrder(event, orderId, userId);
    } else if (action === 'view_orders') {
        result = await viewOrders(event, userId);
    } else {
        result = { error: 'Invalid action specified.' };
    }

    if (result.error) {
        event.reply('#text', { text: result.error });
    } else {
        event.reply('#text', { text: JSON.stringify(result) });
    }
};
