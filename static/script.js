function addToCart(productId) {
    fetch(`/add_to_cart/${productId}`)
        .then(response => {
            if (response.ok) {
                alert('Product added to cart');
            } else {
                alert('Error adding product to cart');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error adding product to cart');
        });
}


document.addEventListener('DOMContentLoaded', function() {
    const chatbotToggleButton = document.getElementById('chatbot-toggle-button');
    const chatbotContainer = document.getElementById('chatbot-container');
    const chatbotHeader = document.getElementById('chatbot-header');
    const chatbotMessages = document.getElementById('chatbot-messages');
    const chatbotInput = document.getElementById('chatbot-input');
    const chatbotSendButton = document.getElementById('chatbot-send-button');

    chatbotContainer.classList.add('hidden');

    chatbotToggleButton.addEventListener('click', function() {
        chatbotContainer.classList.toggle('hidden');
        chatbotToggleButton.classList.add('hidden');

        if (chatbotMessages.children.length === 0) {
            addBotMessage("Hello! I'm your shopping assistant. How can I help you today?");
        }
        chatbotInput.focus();
    });

    chatbotHeader.addEventListener('click', function(e) {
        if (e.target.id !== 'chatbot-close') {
            chatbotContainer.classList.toggle('collapsed');
        }
    });

    document.getElementById('chatbot-close').addEventListener('click', function() {
        chatbotContainer.classList.add('hidden');
        chatbotToggleButton.classList.remove('hidden');
    });

    chatbotSendButton.addEventListener('click', sendMessage);
    chatbotInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    function sendMessage() {
        const message = chatbotInput.value.trim().toLowerCase();
        if (message === '') return;

        addUserMessage(message);
        chatbotInput.value = '';

        fetch('/chatbot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message }),
        })
        .then(response => response.json())
        .then(data => {
            addBotMessage(data.response);

            if (data.redirect) {
                addBotMessage(`Taking you to <a href="${data.redirect}">checkout</a>...`);
                setTimeout(() => {
                    window.location.href = data.redirect;
                }, 1500);
            }

            checkForSpecialCommands(data.response);
        })
        .catch(error => {
            console.error('Error:', error);
            addBotMessage("Sorry, I'm having trouble connecting to the server. Please try again later.");
        });
    }

    function checkForSpecialCommands(response) {
        const products = ["idli mix", "dosa mix", "upma mix", "poha mix", "cake mix", "thandai", "sambar", "rasam", "badam milk"];

        if (response.includes("proceed to checkout") || response.includes("continue shopping")) {
            addQuickReplyButtons([{ text: "Checkout", action: "checkout" }, { text: "Continue Shopping", action: "continue" }]);
        }

        if (response.includes("Your order #") && response.includes("is currently")) {
            if (!response.includes("cancelled")) {
                addQuickReplyButtons([{ text: "Cancel Order", action: "cancel" }]);
            }
        }

        // Detect if user is trying to order a product
        for (let product of products) {
            if (response.includes(product)) {
                addQuickReplyButtons([{ text: `Confirm Order for ${product}`, action: `confirm-${product}` }]);
            }
        }
    }

    function addQuickReplyButtons(buttons) {
        const buttonsContainer = document.createElement('div');
        buttonsContainer.classList.add('quick-reply-buttons');

        buttons.forEach(button => {
            const btn = document.createElement('button');
            btn.textContent = button.text;
            btn.classList.add('quick-reply-button');
            btn.addEventListener('click', function() {
                if (button.action === "checkout") {
                    addUserMessage("Checkout");
                    window.location.href = "/checkout";
                } else if (button.action === "continue") {
                    addUserMessage("Continue shopping");
                    buttonsContainer.remove();
                } else if (button.action.startsWith("confirm-")) {
                    const product = button.action.replace("confirm-", "");
                    addUserMessage(`Confirm order for ${product}`);
                    chatbotInput.value = `Confirm order for ${product}`;
                    sendMessage();
                } else if (button.action === "cancel") {
                    const lastBotMessage = Array.from(chatbotMessages.querySelectorAll('.bot-message')).pop().textContent;
                    const orderMatch = lastBotMessage.match(/order #(\d+)/);
                    if (orderMatch && orderMatch[1]) {
                        const orderNumber = orderMatch[1];
                        addUserMessage(`Cancel order #${orderNumber}`);
                        chatbotInput.value = `Cancel order #${orderNumber}`;
                        sendMessage();
                    } else {
                        addUserMessage("Cancel order");
                        chatbotInput.value = "Cancel order";
                        sendMessage();
                    }
                }

                buttonsContainer.remove();
            });
            buttonsContainer.appendChild(btn);
        });

        chatbotMessages.appendChild(buttonsContainer);
        scrollToBottom();
    }

    function addUserMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', 'user-message');
        messageElement.textContent = message;
        chatbotMessages.appendChild(messageElement);
        scrollToBottom();
    }

    function addBotMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', 'bot-message');
        messageElement.innerHTML = message;
        chatbotMessages.appendChild(messageElement);
        scrollToBottom();
    }

    function scrollToBottom() {
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
    }
});
