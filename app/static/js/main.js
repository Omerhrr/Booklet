// Custom JavaScript will go here// Custom JavaScript will go here

// --- NEW HTMX EXTENSION ---
htmx.defineExtension('update-form-attributes', {
    onEvent: function (name, evt) {
        if (name === 'htmx:configRequest') {
            // Get the element that triggered the request (the button)
            const triggerElement = evt.detail.elt;

            // Check if this extension should be applied
            if (triggerElement.hasAttribute('hx-ext') && triggerElement.getAttribute('hx-ext').includes('update-form-attributes')) {
                
                // Get the target form element
                const targetSelector = triggerElement.getAttribute('hx-target');
                const form = document.querySelector(targetSelector);

                if (form) {
                    // Get the product data from the button's hx-vals
                    const vals = evt.detail.parameters;
                    if (vals.product_id) {
                        // Construct the correct POST URL
                        const postUrl = `/inventory/products/${vals.product_id}/adjust-stock`;
                        // Set the hx-post attribute on the form
                        form.setAttribute('hx-post', postUrl);
                    }
                    if (vals.product_name) {
                        // Find the span for the product name in the modal and update it
                        const productNameSpan = document.getElementById('adjust-stock-product-name');
                        if (productNameSpan) {
                            productNameSpan.innerText = vals.product_name;
                        }
                    }
                }
            }
        }
    }
});
