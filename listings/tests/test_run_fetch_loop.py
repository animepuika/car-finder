from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from listings.management.commands.run_fetch_loop import run_one_cycle


class RunOneCycleTests(SimpleTestCase):
    @patch('listings.management.commands.run_fetch_loop.call_command')
    def test_calls_fetch_listings(self, mock_call_command):
        stderr = MagicMock()
        style = MagicMock()

        run_one_cycle(stderr, style)

        mock_call_command.assert_called_once_with('fetch_listings')
        stderr.write.assert_not_called()

    @patch('listings.management.commands.run_fetch_loop.call_command')
    def test_a_failed_cycle_is_caught_not_raised(self, mock_call_command):
        mock_call_command.side_effect = Exception('network error')
        stderr = MagicMock()
        style = MagicMock()
        style.ERROR.side_effect = lambda msg: msg

        run_one_cycle(stderr, style)

        stderr.write.assert_called_once()
        self.assertIn('network error', stderr.write.call_args[0][0])
