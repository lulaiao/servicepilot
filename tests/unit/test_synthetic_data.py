from servicepilot.domain.synthetic import generate_dataset


def test_synthetic_data_is_deterministic_for_seed() -> None:
    first = generate_dataset(seed=17, order_count=12)
    second = generate_dataset(seed=17, order_count=12)
    different = generate_dataset(seed=18, order_count=12)

    assert first == second
    assert first != different
    assert len(first.orders) == 12
    assert all(order.user_id.startswith("synthetic-user-") for order in first.orders)
