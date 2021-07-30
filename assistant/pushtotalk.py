"""Sample that implements a gRPC client for the Google Assistant API."""

import json
import logging
import sys

import google.auth.transport.grpc
import google.auth.transport.requests
import google.oauth2.credentials
import grpc
from google.assistant.embedded.v1alpha2 import (
    embedded_assistant_pb2,
    embedded_assistant_pb2_grpc
)
from tenacity import retry, stop_after_attempt, retry_if_exception

from . import audio_helpers

ASSISTANT_API_ENDPOINT = 'embeddedassistant.googleapis.com'
DEFAULT_GRPC_DEADLINE = 60 * 3 + 5


class SampleAssistant(object):
    """Sample Assistant that supports conversations and device actions.

    Args:
      device_model_id: identifier of the device model.
      device_id: identifier of the registered device instance.
      conversation_stream(ConversationStream): audio stream
        for recording query and playing back assistant answer.
      channel: authorized gRPC channel for connection to the
        Google Assistant API.
      deadline_sec: gRPC deadline in seconds for Google Assistant API call.
      device_handler: callback for device actions.
    """

    def __init__(self, language_code, device_model_id, device_id,
                 conversation_stream, channel, deadline_sec):
        self.language_code = language_code
        self.device_model_id = device_model_id
        self.device_id = device_id
        self.conversation_stream = conversation_stream

        # Create Google Assistant API gRPC client.
        self.assistant = embedded_assistant_pb2_grpc.EmbeddedAssistantStub(
            channel
        )
        self.deadline = deadline_sec

    def is_grpc_error_unavailable(e):
        is_grpc_error = isinstance(e, grpc.RpcError)
        if is_grpc_error and (e.code() == grpc.StatusCode.UNAVAILABLE):
            logging.error('grpc unavailable error: %s', e)
            return True
        return False

    @retry(reraise=True, stop=stop_after_attempt(3),
           retry=retry_if_exception(is_grpc_error_unavailable))
    def assist(self, query, output_filename):
        """Send a voice request to the Assistant and playback the response.

        Returns: True if conversation should continue.
        """
        self.conversation_stream.sink.set_output(open(output_filename, 'wb'))

        def iter_assist_requests():
            config = embedded_assistant_pb2.AssistConfig(
                audio_out_config=embedded_assistant_pb2.AudioOutConfig(
                    encoding='LINEAR16',
                    sample_rate_hertz=audio_helpers.DEFAULT_AUDIO_SAMPLE_RATE,
                    volume_percentage=self.conversation_stream.volume_percentage,
                ),
                dialog_state_in=embedded_assistant_pb2.DialogStateIn(
                    language_code=self.language_code,
                    conversation_state=None,
                    is_new_conversation=True,
                ),
                device_config=embedded_assistant_pb2.DeviceConfig(
                    device_id=self.device_id,
                    device_model_id=self.device_model_id,
                ),
                text_query=query
            )

            yield embedded_assistant_pb2.AssistRequest(config=config)

        # This generator yields AssistResponse proto messages
        # received from the gRPC Google Assistant API.
        for resp in self.assistant.Assist(iter_assist_requests(),
                                          self.deadline):
            if len(resp.audio_out.audio_data) > 0:
                if not self.conversation_stream.playing:
                    self.conversation_stream.start_playback()
                self.conversation_stream.write(resp.audio_out.audio_data)

        self.conversation_stream.stop_playback()


def create_assistant(device_model_id, device_id, credentials="./credentials.json",
           api_endpoint=ASSISTANT_API_ENDPOINT, lang='en-US', verbose=False,
           audio_sample_rate=audio_helpers.DEFAULT_AUDIO_SAMPLE_RATE,
           audio_sample_width=audio_helpers.DEFAULT_AUDIO_SAMPLE_WIDTH,
           audio_iter_size=audio_helpers.DEFAULT_AUDIO_ITER_SIZE,
           grpc_deadline=DEFAULT_GRPC_DEADLINE):

    # Setup logging.
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)

    # Load OAuth 2.0 credentials.
    try:
        with open(credentials, 'r') as f:
            credentials = google.oauth2.credentials.Credentials(token=None,
                                                                **json.load(f))
            http_request = google.auth.transport.requests.Request()
            credentials.refresh(http_request)
    except Exception as e:
        logging.error('Error loading credentials: %s', e)
        logging.error('Run google-oauthlib-tool to initialize '
                      'new OAuth 2.0 credentials.')
        sys.exit(-1)

    # Create an authorized gRPC channel.
    grpc_channel = google.auth.transport.grpc.secure_authorized_channel(
        credentials, http_request, api_endpoint)
    logging.info('Connecting to %s', api_endpoint)

    # Configure audio source and sink.
    audio_sink = audio_helpers.WaveSink(
        sample_rate=audio_sample_rate,
        sample_width=audio_sample_width
    )

    # Create conversation stream with the given audio source and sink.
    conversation_stream = audio_helpers.ConversationStream(
        sink=audio_sink,
        iter_size=audio_iter_size,
        sample_width=audio_sample_width,
    )

    return SampleAssistant(lang, device_model_id, device_id,
                         conversation_stream, grpc_channel, grpc_deadline)
