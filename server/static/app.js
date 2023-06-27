const App = {
    apiUrl: window.env.API_URL,
    state: {
        interaction_id: '',
    },
    $: {
        inputEl: document.getElementById('queryInput'),
        feedbackSpan: document.getElementById('feedbackSpan'),
        responseDiv: document.querySelector('.response'),
        cacheInfo: document.getElementById('cache-info'),
        readmore: document.getElementById('readmore'),
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
        showProgressbar: () => {
            App.$.responseDiv.innerHTML = "<progress></progress>";
        },
        hideProgressbar: () => {
            const pb = App.$.responseDiv.querySelector('progress');
            App.$.responseDiv.removeChild(pb);
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
        appendResponseDivText: (str) => {
            App.$.responseDiv.textContent += str;
        },
        showCacheInfoSpan: () => {
            App.$.cacheInfo.style.display = 'block';
        },
        hideCacheInfoSpan: () => {
            App.$.cacheInfo.style.display = 'none';
        },
        setCacheInfoSpanText: (str) => {
            App.$.cacheInfo.textContent = str;
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
        App.$.hideCacheInfoSpan();
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
                const message = data.message;
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
            App.$.showProgressbar();
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
                if (data.from_cache && data.from_cache === 'true') {
                    App.$.setCacheInfoSpanText(`OBS: Svaret på din fråga levereras direkt från vår cache (snabbminne). Detta sker när en fråga är väldigt lik en tidigare ställd fråga. Det hjälper oss att leverera svar snabbare och effektivare. Den ursprungliga frågan, från vilken vi återanvände svaret, var:  "${data.original_query}"`);
                    App.$.showCacheInfoSpan();
                }
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