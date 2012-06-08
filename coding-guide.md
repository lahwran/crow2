Coding Guide for Contributors
-----------------------------

A few things which I consider mostly common sense:

- Try to follow PEP20 and PEP8 as much as possible. Always use four spaces
   for indent.
- Commit messages should always be a summary in the present tense; write your commit
   messages as though you are titling a pull request. Commit messages must
   have no more than 70 characters on the first line, and preferably no more
   than 50 characters on the first line. If your commit is complex enough to
   warrant it, a more thorough description should be included on line 3. No line
   should be wider than 70 characters.
- There should be one change per commit where possible. If in doubt about the relevance
   of a change hunk to a commit, split your changes into multiple commits.
- Try to avoid committing broken code.
- Avoid committing untested code; never commit code that has not been tested either
   manually or in an automatic test, preferably automatic although if you commit code
   which is not being automatically tested, always manually test it.
- If you make a change to existing code, at least one test should fail. If no tests
   fail, the code was not being sufficiently tested, which should be fixed immediately.
