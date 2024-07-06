const App = {
    apiUrl: window.env.API_URL,
    state: {
        interaction_id: '',
        locale: {}
    },
    $: {
        appHeader: document.getElementById('app-header'),
        intro: document.getElementById('intro'),
        loggingInfo: document.getElementById('logging-info'),
        inputEl: document.getElementById('queryInput'),
        feedbackSpan: document.getElementById('feedbackSpan'),
        responseDiv: document.querySelector('.response'),
        cacheInfo: document.getElementById('cache-info'),
        updatedInfo: document.getElementById('updated-info'),
        updatedInfoHeader: document.getElementById('updated-info-header'),
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
            App.$.responseDiv.innerHTML = `<span aria-busy='true'>${App.state.locale.progressbar_info}</span>`;
        },
        hideProgressbar: () => {
            const pb = App.$.responseDiv.querySelector('progress');
            App.$.responseDiv.removeChild(pb);
        },
        enableInput: () => {
            App.$.inputEl.disabled = false;
        },
        setInputElPlaceholder: (str) => {
            App.$.inputEl.placeholder = str;
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
        showUpdatedInfoSpan: () => {
            App.$.updatedInfo.style.display = 'block';
        },
        hideCacheInfoSpan: () => {
            App.$.cacheInfo.style.display = 'none';
        },
        hideUpdatedInfoSpan: () => {
            App.$.updatedInfo.style.display = 'none';
        },
        setAppHeaderSpanText: (str) => {
            App.$.appHeader.textContent = str;
        },
        setIntro: (str) => {
            App.$.intro.innerHTML = str;
        },
        setLoggingInfoSpanText: (str) => {
            App.$.loggingInfo.textContent = str;
        },
        setCacheInfoSpanText: (str) => {
            App.$.cacheInfo.textContent = str;
        },
        setUpdatedInfoSpanText: (str) => {
            App.$.updatedInfo.textContent = str;
        },
        setUpdatedInfoHeaderSpanText: (str) => {
            App.$.updatedInfoHeader.textContent = str;
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
        App.$.hideUpdatedInfoSpan();
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
            App.$.setResponseDivText(App.state.locale.validation.min_length);
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
                    App.$.setCacheInfoSpanText(`${App.state.locale.cache_info_intro} ${data.original_query}`);
                    App.$.showCacheInfoSpan();
                }
                App.$.showFeedbackSpan();
                if (data.sectionHeaders && data.sectionHeaders.length > 0) {
                    App.$.appendReadmoreHtml(`${App.state.locale.read_more}:<br/>`);
                    data.sectionHeaders.forEach(s => {
                        App.$.appendReadmoreHtml(`${s}<br/>`);
                    });
                }
                if (data.embeddings_version) {
                    App.$.setUpdatedInfoSpanText(`${App.state.locale.updated_source_with_placeholder_for_embver.replace('PLACEHOLDER', data.embeddings_version)}`);
                    App.$.showUpdatedInfoSpan();
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
    displayEmbeddingsUpdatedAtInfo: async () => {
        const response = await fetch(App.apiUrl + 'embeddings_version', {
            method: 'GET',
        });
        if (response.ok) {
            const data = await response.json();
            if (data && data.version) {
                App.$.setUpdatedInfoHeaderSpanText(`${App.state.locale.updated_source_with_placeholder_for_embver.replace('PLACEHOLDER', data.version)}`);
            }
        }
    },
    loadLocaleAndSetUITexts: async () => {
        const response = await fetch(App.apiUrl + 'locale', {
            method: 'GET',
        });
        if (response.ok) {
            const data = await response.json();
            App.state.locale = data;
            App.$.setIntro(App.state.locale.intro)
            App.$.setUpdatedInfoHeaderSpanText(App.state.locale.updated_source)
            App.$.setLoggingInfoSpanText(App.state.locale.logging_info)
            App.$.setAppHeaderSpanText(App.state.locale.app_header)
            App.$.setInputElPlaceholder(App.state.locale.textbox_placeholder)
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
        App.loadLocaleAndSetUITexts();
        App.displayEmbeddingsUpdatedAtInfo();
        App.wireEvents();
        App.$.renderFeedbackSpan();
    }

}
App.init();
