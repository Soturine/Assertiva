package demo.notes;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class NoteValidatorTest {
    @Test
    public void acceptsAShortTitle() {
        assertTrue(NoteValidator.acceptsTitle("Groceries"));
    }

    @Test
    public void rejectsBlankAndOversizedTitles() {
        assertFalse(NoteValidator.acceptsTitle("   "));
        assertFalse(NoteValidator.acceptsTitle("x".repeat(NoteValidator.MAX_TITLE + 1)));
    }
}
