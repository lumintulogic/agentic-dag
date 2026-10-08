import unittest
from fastapi.testclient import TestClient
from src.web import app


class TestVisualizePage(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_visualize_endpoint_and_toggle_connections(self):
        response = self.client.get("/visualize")
        self.assertEqual(response.status_code, 200)
        content = response.text

        # Ensure toggle button and connection elements are present
        self.assertIn('id="toggle-connections"', content)
        self.assertIn('id="connections"', content)

        # Ensure CSS rule for hiding SVG connections exists
        self.assertIn("#connections[hidden]", content)

        # Ensure proper visibility update function exists
        self.assertIn("updateConnectionsVisibility", content)

        # Ensure toggle event listener calls visibility update and schedules redraw
        self.assertIn("updateConnectionsVisibility();", content)
        self.assertIn("scheduleConnections();", content)


    def test_visualize_toggle_parked_cards(self):
        response = self.client.get("/visualize")
        self.assertEqual(response.status_code, 200)
        content = response.text

        # Ensure toggle button for parked cards is present
        self.assertIn('id="toggle-parked-label"', content)

        # Ensure parked card label helpers and update functions exist
        self.assertIn("getParkedCardLabel", content)
        self.assertIn("updateParkedCardsDisplay", content)

        # Ensure parked card toggle event listener calls display update and schedules redraw
        self.assertIn("updateParkedCardsDisplay();", content)
        self.assertIn("scheduleConnections();", content)

        # Ensure syncOffscreenDocks uses getParkedCardLabel
        self.assertIn("getParkedCardLabel(cardId", content)


if __name__ == "__main__":
    unittest.main()
