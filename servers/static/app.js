const App = {
    apiUrl: window.env.API_URL,
    state: {
        interaction_id: '',
    },
    $: { // working with DOM in this namespace
        appEl: document.getElementById('app'),
        inputEl: document.getElementById('queryInput'),
        feedbackSpan: document.getElementById('feedbackSpan'),
        responseDiv: document.querySelector('.response'),
        readmore: document.getElementById('readmore'),
        responseMsg: document.querySelector('.response .responseMsg'),
        renderFeedbackSpan: () => {
            App.$.feedbackSpan.innerHTML = `
                <img src="./static/thumbsUp.png" onClick="App.sendFeedback('thumbsup')" class="feedbackButton" />
                <img src="./static/thumbsDown.png" onClick="App.sendFeedback('thumbsdown')" class="feedbackButton" />`
        },
        showFeedbackSpan: () => {
            App.$.feedbackSpan.style.display = 'block';
        },
        hideFeedbackSpan: () => {
            App.$.feedbackSpan.style.display = 'none';
        },
        enableInput: () => {
            App.$.inputEl.disabled = false;
        },
        disableInput: () => {
            App.$.inputEl.disabled = true;
        },
        setResponseDivText: (str) => {
            App.$.responseDiv.textContent = str;
        },
        setResponseDivHtml: (str) => {
            App.$.responseDiv.innerHTML = str;
        },
        setFeedbackSpanText: (str) => {
            App.$.feedbackSpan.textContent = str;
        },
        setFeedbackSpanHtml: (str) => {
            App.$.feedbackSpan.innerHTML = str;
        },
        setReadmoreHtml: (str) => {
            App.$.readmore.innerHTML = str;
        },
        appendReadmoreHtml: (str) => {
            App.$.readmore.innerHTML += str;
        }

    },
    reset: () => {
        App.$.setReadmoreHtml('');
        App.$.hideFeedbackSpan();
    },
    sendFeedback: async (str) => {
        try {
            const response = await fetch(App.apiUrl + 'feedback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    "interaction_id": App.state.interaction_id,
                    "feedback": str
                })
            });
            if (response.ok) {
                const data = await response.json();
                message = data.message;
                App.$.setFeedbackSpanHtml(`<strong>${message}</strong>`);
                setTimeout(() => {
                    App.$.hideFeedbackSpan();
                    App.$.renderFeedbackSpan(); // re-render feedback span
                }, 3000);
            } else {
                console.error(`Error: ${response.status} ${response.statusText}`);
                const data = await response.json();
                if (data && data.message)
                    App.$.setFeedbackSpanText(data.message);
            }
        } catch (error) {
            console.error("Error fetching data:", error);
            let errorData;
            try {
                errorData = JSON.parse(error.message);
            } catch (parseError) {
                console.error("Could not parse error message:", parseError);
            }
            if (errorData && errorData.message) {
                App.$.setFeedbackSpanText(errorData.message);
            }
        }
    },
    sendQuery: async () => {
        const query = App.$.inputEl.value.trim();
        if (query.length < 1) {
            App.$.setResponseDivText("Du måste ställa en fråga...");
            return;
        }

        try {
            App.$.setResponseDivHtml("<progress></progress>"); // show progress bar
            App.$.disableInput();
            const response = await fetch(App.apiUrl + 'qa', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    "query": query
                })
            });
            if (response.ok) {
                const data = await response.json();
                App.state.interaction_id = data.interaction_id;
                App.$.setResponseDivText(data.message); // textContent does not parse HTML (safer when presenting response from LLM)
                App.$.showFeedbackSpan();
                if (data.sectionHeaders && data.sectionHeaders.length > 0) {
                    App.$.appendReadmoreHtml('Läs mer:<br/>');
                    data.sectionHeaders.forEach(s => {
                        App.$.appendReadmoreHtml(`${s}<br/>`);
                    });
                }
            } else {
                console.error(`Error: ${response.status} ${response.statusText}`);
                const data = await response.json();
                if (data && data.message)
                    App.$.setResponseDivText(data.message);
            }
        } catch (error) {
            console.error("Error fetching data:", error);
            let errorData;
            try {
                errorData = JSON.parse(error.message);
            } catch (parseError) {
                console.error("Could not parse error message:", parseError);
            }
            if (errorData && errorData.message) {
                App.$.setResponseDivText(errorData.message);
            }
        }
        finally {
            App.$.enableInput();
        }
    },
    wireEvents: () => {
        App.$.inputEl.addEventListener('keydown', async (e) => {
            if (e.code === 13 || e.key === 'Enter') {
                e.preventDefault();
                App.reset();
                App.sendQuery();
            }
        });
    },
    init: () => {
        App.wireEvents();
        App.$.renderFeedbackSpan();
    }

}
App.init();