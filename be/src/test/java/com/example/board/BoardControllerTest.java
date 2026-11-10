package com.example.board;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

class BoardControllerTest {
    private final BoardStore store = org.mockito.Mockito.mock(BoardStore.class);
    private MockMvc mvc;

    @BeforeEach
    void setUp() { mvc = MockMvcBuilders.standaloneSetup(new BoardController(store)).build(); }

    @Test
    void createsPostWithTrimmedInput() throws Exception {
        when(store.create("제목", "내용")).thenReturn(new BoardStore.Post("1", "제목", "내용", "2026-11-10T00:00:00Z", 0, List.of()));

        mvc.perform(post("/api/posts").contentType(MediaType.APPLICATION_JSON)
                .content("{\"title\":\" 제목 \",\"content\":\" 내용 \"}"))
            .andExpect(status().isCreated()).andExpect(jsonPath("$.title").value("제목"));
        verify(store).create("제목", "내용");
    }

    @Test
    void rejectsBlankPost() throws Exception {
        mvc.perform(post("/api/posts").contentType(MediaType.APPLICATION_JSON)
                .content("{\"title\":\"  \",\"content\":\"내용\"}"))
            .andExpect(status().isBadRequest());
        org.mockito.Mockito.verify(store, org.mockito.Mockito.never()).create(anyString(), anyString());
    }

    @Test
    void addsAnonymousCommentAndLike() throws Exception {
        var updated = new BoardStore.Post("1", "제목", "내용", "2026-11-10T00:00:00Z", 1,
            List.of(new BoardStore.Comment("2", "안녕", "2026-11-10T00:00:01Z")));
        when(store.comment("1", "안녕")).thenReturn(updated);
        when(store.like("1")).thenReturn(updated);

        mvc.perform(post("/api/posts/1/comments").contentType(MediaType.APPLICATION_JSON)
                .content("{\"content\":\"안녕\"}"))
            .andExpect(status().isCreated()).andExpect(jsonPath("$.comments[0].content").value("안녕"));
        mvc.perform(post("/api/posts/1/likes"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.likes").value(1));
    }
}
