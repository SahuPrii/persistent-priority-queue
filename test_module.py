import os
import unittest

from module import PersistentPriorityQueue


class TestPersistentPriorityQueue(unittest.TestCase):
    def setUp(self):
        self.path = "test_pq_storage.json"
        if os.path.exists(self.path):
            os.remove(self.path)
        self.pq = PersistentPriorityQueue(storage_path=self.path)

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_is_empty_initially(self):
        self.assertTrue(self.pq.is_empty())

    def test_insert_and_len(self):
        self.pq.insert(3, "x")
        self.pq.insert(1, "y")
        self.assertEqual(len(self.pq), 2)
        self.assertFalse(self.pq.is_empty())

    def test_peek_min_and_max(self):
        self.pq.insert(5, "A")
        id_b = self.pq.insert(1, "B")
        id_c = self.pq.insert(9, "C")

        self.assertEqual(self.pq.peek("min"), (id_b, 1, "B"))
        self.assertEqual(self.pq.peek("max"), (id_c, 9, "C"))
        # peek must not remove anything
        self.assertEqual(len(self.pq), 3)

    def test_extract_min_order(self):
        self.pq.insert(5, "A")
        self.pq.insert(1, "B")
        self.pq.insert(9, "C")
        self.pq.insert(3, "D")

        results = []
        while not self.pq.is_empty():
            _, priority, value = self.pq.extract_min()
            results.append((priority, value))

        self.assertEqual(results, [(1, "B"), (3, "D"), (5, "A"), (9, "C")])

    def test_extract_max_order(self):
        self.pq.insert(5, "A")
        self.pq.insert(1, "B")
        self.pq.insert(9, "C")
        self.pq.insert(3, "D")

        results = []
        while not self.pq.is_empty():
            _, priority, value = self.pq.extract_max()
            results.append((priority, value))

        self.assertEqual(results, [(9, "C"), (5, "A"), (3, "D"), (1, "B")])

    def test_extract_on_empty_returns_none(self):
        self.assertIsNone(self.pq.extract_min())
        self.assertIsNone(self.pq.extract_max())
        self.assertIsNone(self.pq.peek("min"))

    def test_update_priority_changes_ordering(self):
        id_a = self.pq.insert(5, "A")
        id_b = self.pq.insert(1, "B")

        self.assertEqual(self.pq.peek("min")[0], id_b)

        self.pq.update(id_a, new_priority=0)
        self.assertEqual(self.pq.peek("min")[0], id_a)

    def test_update_value_only(self):
        id_a = self.pq.insert(5, "A")
        ok = self.pq.update(id_a, new_value="A-updated")
        self.assertTrue(ok)
        _, priority, value = self.pq.peek("min")
        self.assertEqual(priority, 5)
        self.assertEqual(value, "A-updated")

    def test_update_nonexistent_returns_false(self):
        self.assertFalse(self.pq.update("does-not-exist", new_priority=1))

    def test_delete(self):
        id_a = self.pq.insert(5, "A")
        id_b = self.pq.insert(1, "B")

        self.assertTrue(self.pq.delete(id_b))
        self.assertFalse(self.pq.delete(id_b))  # already gone
        self.assertEqual(self.pq.peek("min")[0], id_a)
        self.assertEqual(len(self.pq), 1)

    def test_explicit_item_id_and_duplicate_rejection(self):
        self.pq.insert(1, "A", item_id="fixed-id")
        with self.assertRaises(ValueError):
            self.pq.insert(2, "B", item_id="fixed-id")

    def test_persistence_across_restart(self):
        id_a = self.pq.insert(5, "A")
        id_b = self.pq.insert(1, "B")
        self.pq.update(id_a, new_priority=0)
        self.pq.delete(id_b)

        # Simulate a fresh process loading the same storage file.
        reloaded = PersistentPriorityQueue(storage_path=self.path)
        self.assertEqual(len(reloaded), 1)
        item_id, priority, value = reloaded.peek("min")
        self.assertEqual(item_id, id_a)
        self.assertEqual(priority, 0)
        self.assertEqual(value, "A")

    def test_many_operations_stress(self):
        # Insert a bunch, delete/update some, then verify extraction order
        # matches a plain sorted() of what should remain.
        ids = [self.pq.insert(priority=i, value=f"v{i}") for i in range(50)]

        # Delete every 3rd item.
        for i, item_id in enumerate(ids):
            if i % 3 == 0:
                self.pq.delete(item_id)

        # Update every 5th remaining item to a very low priority.
        for i, item_id in enumerate(ids):
            if i % 3 != 0 and i % 5 == 0:
                self.pq.update(item_id, new_priority=-1000 - i)

        expected = []
        for i, item_id in enumerate(ids):
            if i % 3 == 0:
                continue
            priority = -1000 - i if i % 5 == 0 else i
            expected.append(priority)
        expected.sort()

        actual = []
        while not self.pq.is_empty():
            _, priority, _ = self.pq.extract_min()
            actual.append(priority)

        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
