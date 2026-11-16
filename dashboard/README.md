# Lead & model dashboard (Streamlit)

Internal tool for exploring lead scores, the preprocessing pipeline and the linear / logistic
models. It is not part of the production image and its dependencies are not in `pyproject.toml`.

```bash
pip install streamlit altair pandas scikit-learn matplotlib
# data files are git-ignored: put the customers export at data/combined_clients_orders.csv
python backend/scripts/enrich_synthetic_data.py      # optional: SYNTHETIC lead-behaviour columns
streamlit run dashboard/app.py
```

The sidebar toggle "משתני ליד פקטיביים" switches the logistic tab to the synthetic columns.
They are invented: any improvement they show is true by construction.
