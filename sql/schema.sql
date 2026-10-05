PRAGMA foreign_keys = ON;
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    signup_date TEXT NOT NULL,
    platform TEXT NOT NULL CHECK (platform IN ('web','android','ios')),
    acquisition_channel TEXT NOT NULL
);
CREATE TABLE events (
    event_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    session_id INTEGER NOT NULL,
    event_time TEXT NOT NULL,
    event_name TEXT NOT NULL CHECK (event_name IN ('view','add_to_cart','checkout','purchase','payment_error')),
    platform TEXT NOT NULL,
    app_version TEXT NOT NULL
);
CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    session_id INTEGER NOT NULL UNIQUE,
    order_time TEXT NOT NULL,
    amount_kzt INTEGER NOT NULL CHECK (amount_kzt > 0),
    status TEXT NOT NULL CHECK (status = 'paid')
);
CREATE INDEX events_user_time ON events(user_id, event_time);
CREATE INDEX events_session ON events(session_id);

-- Ordered funnel within a session. Later stages require all preceding stages.
CREATE VIEW session_funnel AS
WITH first_view AS (
    SELECT session_id, user_id, platform, app_version, MIN(event_time) AS view_time
    FROM events WHERE event_name = 'view'
    GROUP BY session_id, user_id, platform, app_version
), cart AS (
    SELECT v.*, MIN(e.event_time) AS cart_time
    FROM first_view v LEFT JOIN events e ON e.session_id = v.session_id
        AND e.event_name = 'add_to_cart' AND e.event_time > v.view_time
    GROUP BY v.session_id, v.user_id, v.platform, v.app_version, v.view_time
), checkout AS (
    SELECT c.*, MIN(e.event_time) AS checkout_time
    FROM cart c LEFT JOIN events e ON e.session_id = c.session_id
        AND e.event_name = 'checkout' AND e.event_time > c.cart_time
    GROUP BY c.session_id, c.user_id, c.platform, c.app_version, c.view_time, c.cart_time
)
SELECT c.*, MIN(e.event_time) AS purchase_time
FROM checkout c LEFT JOIN events e ON e.session_id = c.session_id
    AND e.event_name = 'purchase' AND e.event_time > c.checkout_time
GROUP BY c.session_id, c.user_id, c.platform, c.app_version, c.view_time, c.cart_time, c.checkout_time;
