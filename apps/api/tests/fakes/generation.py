from devatlas.application.ports.generation import (
    AnswerGenerationRequest,
    GeneratedAnswer,
)


class RecordingAnswerGenerator:
    def __init__(self, result: GeneratedAnswer) -> None:
        self._result = result
        self.requests: list[AnswerGenerationRequest] = []

    async def generate(self, request: AnswerGenerationRequest) -> GeneratedAnswer:
        self.requests.append(request)
        return self._result
