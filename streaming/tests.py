import json
import os
import tempfile

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings

from .models import LiveSession
from .views import mediamtx_record_webhook


class MediaMtxRecordWebhookTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='teknisi')
        self.session = LiveSession.objects.create(teknisi=self.user, stream_key='abc123')

    def _post(self, segment_path, root):
        payload = {'path': 'live-abc123-rec', 'segment_path': segment_path}
        request = self.factory.post(
            '/streaming/webhook/mediamtx-record/?key=secret',
            data=json.dumps(payload),
            content_type='application/json',
        )
        with override_settings(MEDIAMTX_AUTH_SECRET='secret', STREAMING_RECORDINGS_ROOT=root):
            return mediamtx_record_webhook(request)

    def test_rejects_segment_path_outside_recordings_root(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as other:
            response = self._post(os.path.join(other, 'evil.mp4'), root)
            self.session.refresh_from_db()
            self.assertEqual(response.status_code, 403)
            self.assertEqual(self.session.recording_path, '')

    def test_accepts_segment_path_inside_recordings_root(self):
        with tempfile.TemporaryDirectory() as root:
            segment = os.path.join(root, 'live-abc123-rec.mp4')
            response = self._post(segment, root)
            self.session.refresh_from_db()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.session.recording_path, segment)
