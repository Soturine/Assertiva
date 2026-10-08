package demo.notes;

public final class NoteValidator {
    public static final int MAX_TITLE = 40;

    private NoteValidator() {}

    /** A title is accepted when it has visible text and fits the limit. */
    public static boolean acceptsTitle(String title) {
        return title != null && !title.trim().isEmpty() && title.length() <= MAX_TITLE;
    }
}
