# Data Science Portfolio 📊

Questa repository raccoglie 5 progetti accademici per il corso di Data Science 2024/2025.

**Autori:** Matteo Sonaglioni, Enzo Cingoli, Gabriel Vladut Popa  
**Repository Pubblica:** [MattSona99/DataScience](https://github.com/MattSona99/DataScience)

---

## Indice dei Progetti

1. [NLP: Random Acts of Pizza](#1-nlp-text-classification--information-extraction)
2. [GenAI: Code & Dashboard Generation](#2-genai-tetris--dashboard-prompting)
3. [Social Network Analysis: Donald Trump's Ego Network](#3-social-network-analysis-trump-ego-network)
4. [Chatbot: Videogiochi Vintage](#4-chatbot-vintage-games-recommender)
5. [Crimini a Baltimora: Classification, Clustering & Time Series](#5-baltimore-crimes-classification-clustering--time-series)

---

## 1. NLP: Text Classification & Information Extraction
**Obiettivo:** Analizzare il dataset di Reddit *"Random Acts of Pizza"* per comprendere quali fattori linguistici e semantici portano una richiesta di pizza ad avere successo.

* **Intento:** Il progetto si divide in due task. Il primo è la **Classificazione del Testo** per predire se una richiesta verrà esaudita (ricezione della pizza). Il secondo è l'**Information Extraction** per identificare pattern di persuasione (es. *politeness*, *reciprocity*, narrazione di difficoltà economiche) e feature linguistiche che aumentano la probabilità di successo.
* **Tecnologie & Metodi:**
    * **Preprocessing:** Cleaning avanzato, Lemmatization, POS Tagging.
    * **Feature Engineering:** VADER (Sentiment Analysis), Topic Modeling (NMF), Feature domain-specific (es. parole di gratitudine).
    * **Modelli:** Logistic Regression, Random Forest, Voting Classifier (Ensemble).
    * **Deep Learning:** Uso di BERT Embeddings.

---

## 2. GenAI: Tetris & Dashboard Prompting
**Obiettivo:** Esplorare le capacità dei Large Language Models (LLM) nella generazione di codice funzionale e nel supporto alla Business Intelligence.

* **Intento:** Il progetto dimostra l'efficacia del *Prompt Engineering* iterativo in due scenari:
    1.  **Software Development:** Creazione da zero di un clone del videogioco *Tetris* (in stile "Gothic") perfettamente funzionante in Python.
    2.  **Dashboarding:** Generazione e raffinamento di dashboard aziendali partendo da uno schema ER, utilizzando un Chatbot (ChitChat) per correggere errori di visualizzazione, calcolo KPI e design.
* **Tecnologie & Metodi:**
    * **LLM:** Gemini Pro / ChatGPT.
    * **Librerie:** Python, Pygame.
    * **Metodologia:** Chain-of-thought prompting, raffinamento iterativo degli output.

---

## 3. Social Network Analysis: Trump Ego Network
**Obiettivo:** Analizzare la struttura di potere e le relazioni nell'Ego Network di Donald J. Trump (anno 2018).

* **Intento:** Studiare la topologia della rete per identificare gli attori chiave (*Key Players*), i *Gatekeeper* e le comunità latenti. L'analisi mira a dimostrare come la rete sia strutturata secondo un modello "Hub-and-Spoke", caratterizzato da alta centralizzazione sull'Ego e bassa resilienza strutturale (frammentazione in assenza del leader).
* **Tecnologie & Metodi:**
    * **Librerie:** NetworkX, Pandas, Matplotlib/Seaborn.
    * **Metriche:** Centrality (Degree, Betweenness, Eigenvector, PageRank).
    * **Algoritmi:** Greedy Modularity (Community Detection), Layout Force-Directed (Kamada-Kawai).

---

## 4. Chatbot: Vintage Games Recommender
**Obiettivo:** Sviluppare un assistente conversazionale per la ricerca e raccomandazione di videogiochi pubblicati tra il 2004 e il 2010.

* **Intento:** Creare un'interfaccia in linguaggio naturale che permetta agli utenti di filtrare un database di videogiochi basandosi su criteri complessi (genere, console, rating, feature specifiche). Il bot gestisce il flusso di dialogo, riconosce le entità (es. "Nintendo DS", "Action") e gestisce casi di errore o "no results".
* **Tecnologie & Metodi:**
    * **Framework:** Rasa (Open Source).
    * **Pipeline NLU:** DIETClassifier per Intent Recognition & Entity Extraction.
    * **Dataset:** Managerial and Decision Economics 2013 Video Games Dataset.
    * **Logica:** Gestione Slot, Custom Actions in Python, Forms.

---

## 5. Baltimore Crimes: Classification, Clustering & Time Series
**Obiettivo:** Un'analisi completa a 360° del dataset sui crimini di Baltimora (2010-2017) applicando tre diverse metodologie di Data Science.

* **Intento:**
    1.  **Classification:** Predire l'arma utilizzata nel crimine (es. *Firearm*, *Knife*, *Hands*) gestendo il forte sbilanciamento delle classi.
    2.  **Clustering:** Profilare i distretti di polizia per identificare zone con pattern criminali simili (es. "distretti di rapine armate" vs "distretti di aggressioni diurne").
    3.  **Time Series:** Prevedere il numero settimanale di incidenti futuri analizzando trend e stagionalità.
* **Tecnologie & Metodi:**
    * **Classificazione:** Random Forest, Gradient Boosting, SMOTEENN (per bilanciamento dati).
    * **Clustering:** K-Means, PCA (riduzione dimensionale), DBSCAN (rilevamento Hotspots geografici).
    * **Time Series:** Decomposizione stagionale, Test ADF (stazionarietà), Modelli SARIMAX.
