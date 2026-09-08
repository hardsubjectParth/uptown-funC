import re, subprocess, sys
from pathlib import Path
from docx import Document


class ToolRegistry:
    def __init__(self, workspace, rag=None):
        self.workspace = workspace
        self.rag = rag

    def names(self):
        return [
            'search_documents',
            'read_file',
            'write_file',
            'generate_docx',
        ]

    def execute(self, jid, name, args):
        if name == 'search_documents':
            q = args.get('query', '').lower()
            if self.rag:
                hits = self.rag.search_sync(q, args.get('top_k', 5), args.get('metadata'))
                return {
                    'hits': hits,
                    'count': len(hits),
                    'sources': [{'name': hit['source'], 'source': hit['source']} for hit in hits],
                }
            hits = []

            input_root = self.workspace.root / jid / 'input'

            if input_root.exists():
                for p in input_root.rglob('*'):
                    if (
                        p.is_file()
                        and p.suffix.lower() in {'.txt', '.md'}
                    ):
                        t = p.read_text(errors='ignore')

                        if q in t.lower() or not q:
                            hits.append({
                                'name': p.name,
                                'snippet': t[:500],
                                'source': str(
                                    p.relative_to(
                                        self.workspace.root / jid
                                    )
                                ),
                            })

            return {
                'hits': hits,
                'count': len(hits),
                'sources': [
                    {
                        'name': h['name'],
                        'source': h['source'],
                    }
                    for h in hits
                ],
            }

        if name == 'read_file':
            return {
                'text': self.workspace.safe(
                    jid,
                    args['path']
                ).read_text(errors='ignore')
            }

        if name == 'write_file':
            p = self.workspace.safe(
                jid,
                args['path'],
                True
            )

            p.write_text(
                args.get('content', '')
            )

            return {
                'path': str(
                    p.relative_to(
                        self.workspace.root / jid
                    )
                )
            }

        if name == 'generate_docx':
            p = self.workspace.safe(
                jid,
                'output/' + args.get(
                    'filename',
                    'approval_note.docx'
                ),
                True
            )

            d = Document()

            d.add_heading(
                args.get(
                    'title',
                    'Approval Note'
                ),
                0
            )

            for s in args.get('sections', []):
                d.add_heading(
                    s.get(
                        'heading',
                        'Section'
                    ),
                    1
                )

                d.add_paragraph(
                    s.get(
                        'body',
                        ''
                    )
                )

            citations = args.get('citations', [])

            if citations:
                d.add_heading(
                    'References',
                    1
                )

                for citation in citations:
                    d.add_paragraph(
                        str(citation)
                    )

            d.save(p)

            return {
                'path': str(
                    p.relative_to(
                        self.workspace.root / jid
                    )
                ),
                'name': p.name,
                'mime_type': (
                    'application/vnd.openxmlformats-officedocument'
                    '.wordprocessingml.document'
                ),
                'citations': citations,
            }

        raise ValueError('UNKNOWN_TOOL')