"""Deterministic synthetic e-commerce telemetry. No real customer data."""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
START = pd.Timestamp('2026-06-01')
END = pd.Timestamp('2026-09-30')
SEED = 42


def generate():
    rng = np.random.default_rng(SEED)
    users, events, orders = [], [], []
    session_id = 0
    for user_id in range(1, 3001):
        signup = START + pd.Timedelta(days=int(rng.integers(0, 92)))
        platform = str(rng.choice(['web', 'android', 'ios'], p=[.40, .35, .25]))
        channel = str(rng.choice(['organic', 'direct', 'paid_search', 'paid_social'], p=[.30, .20, .30, .20]))
        users.append((user_id, signup.strftime('%Y-%m-%d'), platform, channel))
        habit = float(rng.uniform(.6, 1.4))
        for day in pd.date_range(signup, END):
            age = (day - signup).days
            return_prob = min(.65, habit * (.20 * np.exp(-age / 20) + .055))
            if age > 0 and rng.random() >= return_prob:
                continue
            session_id += 1
            # One session per user per UTC calendar day, deliberately simplifying attribution.
            ts = day + pd.Timedelta(hours=int(rng.integers(8, 21)), minutes=int(rng.integers(0, 45)))
            version = 'web' if platform == 'web' else '2.0'
            if platform == 'android' and day >= pd.Timestamp('2026-09-01') and rng.random() < .75:
                version = '2.1'

            def emit(name, offset):
                events.append((len(events) + 1, user_id, session_id, (ts + pd.Timedelta(seconds=offset)).strftime('%Y-%m-%d %H:%M:%S'), name, platform, version))

            emit('view', 0)
            cart_prob = {'organic': .48, 'direct': .50, 'paid_search': .43, 'paid_social': .32}[channel]
            if rng.random() >= cart_prob:
                continue
            emit('add_to_cart', 60)
            if rng.random() >= .72:
                continue
            emit('checkout', 120)
            # Planted anomaly: checkout failure after Android 2.1 rollout.
            purchase_prob = .40 if version == '2.1' else .76
            if rng.random() < purchase_prob:
                emit('purchase', 180)
                amount = int(np.clip(rng.lognormal(np.log(18000), .55), 2000, 120000))
                orders.append((len(orders) + 1, user_id, session_id, (ts + pd.Timedelta(seconds=180)).strftime('%Y-%m-%d %H:%M:%S'), amount, 'paid'))
            else:
                emit('payment_error', 180)

    frames = {
        'users': pd.DataFrame(users, columns=['user_id', 'signup_date', 'platform', 'acquisition_channel']),
        'events': pd.DataFrame(events, columns=['event_id', 'user_id', 'session_id', 'event_time', 'event_name', 'platform', 'app_version']),
        'orders': pd.DataFrame(orders, columns=['order_id', 'user_id', 'session_id', 'order_time', 'amount_kzt', 'status']),
    }
    (ROOT / 'data').mkdir(exist_ok=True)
    for name, frame in frames.items():
        frame.to_csv(ROOT / 'data' / f'{name}.csv', index=False)
        frame.to_csv(ROOT / 'data' / f'{name}.csv.gz', index=False,
                     compression={'method':'gzip','mtime':0})
    return frames


if __name__ == '__main__':
    print({name: len(df) for name, df in generate().items()})
