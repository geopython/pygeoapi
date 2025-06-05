--
-- PostgreSQL database dump
--

-- Dumped from database version 13.3 (Debian 13.3-1.pgdg110+1)
-- Dumped by pg_dump version 13.3 (Debian 13.3-1.pgdg110+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: foo; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.foo (
    id integer NOT NULL,
    field1 numeric(4,3),
    field2 bytea,
    dt timestamp without time zone,
    the_geom public.geometry(Point,4326),
    field3 numeric
);


ALTER TABLE public.foo OWNER TO postgres;

--
-- Name: foo_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.foo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.foo_id_seq OWNER TO postgres;

--
-- Name: foo_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.foo_id_seq OWNED BY public.foo.id;


--
-- Name: foo id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.foo ALTER COLUMN id SET DEFAULT nextval('public.foo_id_seq'::regclass);


--
-- Data for Name: foo; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.foo (id, field1, field2, dt, the_geom, field3) FROM stdin;
1	2.100	\\x746f6d	2000-11-11 11:11:11	0101000020E610000000000000008052C00000000000804640	232.1
\.


--
-- Name: foo_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.foo_id_seq', 1, true);


--
-- Name: TABLE foo; Type: ACL; Schema: public; Owner: postgres
--

GRANT SELECT ON TABLE public.foo TO replicator;


--
-- PostgreSQL database dump complete
--
