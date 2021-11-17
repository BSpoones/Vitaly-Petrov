CREATE TABLE IF NOT EXISTS Lessons (
    LessonID integer PRIMARY KEY,
    GroupID integer,
    TeacherID integer,
    DayOfWeek integer,
    StartHour integer,
    StartMin integer,
    EndHour integer,
    EndMin integer,
    Room text
);

CREATE TABLE IF NOT EXISTS Teachers (
    TeacherID integer PRIMARY KEY,
    GroupID integer,
    TeacherName text,
    TeacherSubject text,
    TeacherColour text,
    TeacherLink text

);

CREATE TABLE IF NOT EXISTS Groups (
    GroupID integer PRIMARY KEY,
    GroupOwnerID integer,
    GuildID integer,
    GroupCode text,
    GroupName text,
    RoleID integer,
    Colour text,
    CategoryID integer,
    LessonAnnouncementID integer,
    NLDayID integer,
    NLTimeID integer,
    ImageLink text,
    AlertTimes text

);

CREATE TABLE IF NOT EXISTS Students (
    StudentID integer PRIMARY KEY,
    GroupID integer,
    UserID integer,
    FullName text
);

CREATE TABLE IF NOT EXISTS MessageLogs (
    UserID text,
    GuildID text,
    ChannelID text,
    MessageContent text,
    TimeSent text DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS CommandLogs (
    UserID text,
    GuildID text,
    ChannelID text,
    Command text,
    Args text DEFAULT Null,
    TimeSent text DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Reminders (
    ReminderID integer PRIMARY KEY,
    CreatorUserID text,
    TargetID text,
    OutputGuildID text,
    OutputChannelID text,
    ReminderType text,
    DateType text,
    ReminderDate text,
    ReminderTime text,
    ReminderContent text,
    TimeSent text DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Assignments (
    AssignmentID integer PRIMARY KEY,
    CreatorUserID text,
    GroupID integer,
    TeacherID integer,
    DueDate text,
    DueTime text,
    AssignmentContent text,
    TimeSent text DEFAULT CURRENT_TIMESTAMP
);