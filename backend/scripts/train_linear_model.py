"""Preprocess the orders export and train a linear regression that predicts the order total.

Order of operations (course spec):
  1. Missing data   SimpleImputer(mean) on numeric columns
  2. Scaling        MinMaxScaler to [0, 1]
  3. Encoding       OneHotEncoder on categorical columns
  4. Outliers       IQR rule (1.5 * IQR) on numeric columns and the target
  5. Split          80% train / 20% test
  6. Train          LinearRegression

Usage (from backend/):  python scripts/train_linear_model.py [input.csv] [output.csv]
"""

import sys
from pathlib import Path

import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
NUMERIC = ["adults", "children", "vegetarian_guests", "vegan_guests", "restricted_guests"]
CATEGORICAL = ["event_type", "menu_kashrut", "fulfillment_type", "delivery_city"]
# subtotal / delivery_fee / item_count are excluded: they are components of the target (leakage).
TARGET = "total"
RANDOM_STATE = 42


def load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    df = df[df["order_id"].notna()].copy()  # customers without orders have no target
    df[CATEGORICAL] = df[CATEGORICAL].fillna("לא ידוע")  # missing category becomes its own value
    return df[[*NUMERIC, *CATEGORICAL, TARGET]]


def iqr_mask(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    q1, q3 = frame[columns].quantile(0.25), frame[columns].quantile(0.75)
    iqr = q3 - q1
    inside = (frame[columns] >= q1 - 1.5 * iqr) & (frame[columns] <= q3 + 1.5 * iqr)
    return inside.all(axis=1)


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    numeric = [*NUMERIC, TARGET]
    # 1. Missing values -> column mean
    df[numeric] = SimpleImputer(strategy="mean").fit_transform(df[numeric])
    # 2. Scale to 0-1
    df[numeric] = MinMaxScaler().fit_transform(df[numeric])
    # 3. One-hot encode categorical columns
    encoder = OneHotEncoder(sparse_output=False)
    encoded = pd.DataFrame(
        encoder.fit_transform(df[CATEGORICAL]),
        columns=encoder.get_feature_names_out(CATEGORICAL),
        index=df.index,
    )
    df = pd.concat([encoded, df[numeric]], axis=1)
    # 4. Drop IQR outliers (numeric columns only; the one-hot columns are binary)
    kept = df[iqr_mask(df, numeric)]
    print(f"outliers removed: {len(df) - len(kept)} of {len(df)} rows")
    return kept


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA_DIR / "combined_clients_orders.csv"
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else DATA_DIR / "orders_preprocessed.csv"

    processed = preprocess(load(source))
    processed.to_csv(target, index=False, encoding="utf-8-sig")
    print(f"saved {processed.shape[0]} rows x {processed.shape[1]} columns -> {target}")

    X, y = processed.drop(columns=TARGET), processed[TARGET]
    # 5. 80/20 split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE
    )
    # 6. Train
    model = LinearRegression().fit(X_train, y_train)
    for name, features, actual in (("train", X_train, y_train), ("test", X_test, y_test)):
        predicted = model.predict(features)
        print(
            f"{name}: R2={r2_score(actual, predicted):.3f}  "
            f"MAE={mean_absolute_error(actual, predicted):.4f} (scaled 0-1)"
        )
    top = pd.Series(model.coef_, index=X.columns).sort_values(key=abs, ascending=False).head(8)
    print("strongest coefficients:\n", top.round(3).to_string())


if __name__ == "__main__":
    main()
